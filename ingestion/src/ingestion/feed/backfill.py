# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""One-time backfill of the parliament feed for a deployed environment.

The weekly job keeps the last two weeks current; this fills the weeks before
it, once per environment, before the web that shows the feed is deployed
there. It is the same build as the job (``build_and_publish``), with a longer
window (``--since`` a date, or ``--weeks``) and without the job's time cap,
run from a workstation.

``--plan`` reads the corpus, the protocols and the stored items and lists,
per parliament and week, how many items exist and how many still need
building. It makes no LLM calls and writes nothing. Without it the command asks for confirmation
(prod: the project id), then builds, translates, indexes and stores every
missing item. Items already built are skipped, so it is safe to stop and run
again; an item that failed is retried on the next run.

Usage (from the repo root, with that environment's Qdrant exported):
    QDRANT_URL=... QDRANT_API_KEY=... make backfill-feed TARGET=dev ARGS="--plan --since 2026-09-01"
    QDRANT_URL=... QDRANT_API_KEY=... make backfill-feed TARGET=dev ARGS="--since 2026-09-01"
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time. override=False keeps exported
# variables (make, the shell) in force.
if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import json
import logging
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from qdrant_client import QdrantClient

from ingestion.feed.builder import FeedBuilder, plan_days
from ingestion.feed.bulk import ParliamentRun, build_and_publish, load_sources
from ingestion.feed.index import FEED_COLLECTION_NAME, setup_feed_collection
from ingestion.feed.models import FeedItem
from ingestion.feed.parliaments import FEED_PARLIAMENTS, PARLIAMENTS, Parliament
from ingestion.feed.store import read_items_since
from ingestion.feed.translate import needs_translation
from ingestion.firestore_guard import guard_firestore_target
from ingestion.setup_collection import COLLECTION_NAME, check_fingerprint

logger = logging.getLogger(__name__)

Target = Literal["dev", "prod"]

FIREBASE_PROJECTS: dict[str, str] = {"dev": "wahl-chat-dev", "prod": "wahl-chat"}
_KEY_FILES: dict[str, str] = {
    "dev": "wahl-chat-dev-firebase-adminsdk.json",
    "prod": "wahl-chat-firebase-adminsdk.json",
}
_REPO_ROOT = Path(__file__).resolve().parents[4]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}


def check_target(target: Target, qdrant_url: str) -> list[str]:
    """Why this process must not write ``target``'s feed; empty when it may.

    The collection names freeze at import from ``ENV``, and a forgotten export
    leaves ``QDRANT_URL`` on the local store from ``.env``: either would
    build one environment's feed from another one's corpus.
    """
    problems = []
    if os.getenv("ENV") != target:
        problems.append(f"ENV is {os.getenv('ENV')!r}, expected {target!r}")
    if COLLECTION_NAME != f"wahlchat_chunks_{target}":
        problems.append(f"corpus collection is {COLLECTION_NAME!r}")
    if FEED_COLLECTION_NAME != f"wahlchat_feed_{target}":
        problems.append(f"feed collection is {FEED_COLLECTION_NAME!r}")
    if (urlparse(qdrant_url).hostname or "") in _LOCAL_HOSTS:
        problems.append(
            f"QDRANT_URL points at a local store ({qdrant_url}); export the "
            f"{target} cluster's QDRANT_URL and QDRANT_API_KEY"
        )
    return problems


def key_file(target: Target, explicit: Optional[Path]) -> Optional[Path]:
    """The admin-SDK key to use: the given one, else the usual file name in
    ``ingestion/`` or ``ai-backend/``. None falls back to gcloud ADC."""
    if explicit is not None:
        return explicit
    for folder in ("ingestion", "ai-backend"):
        candidate = _REPO_ROOT / folder / _KEY_FILES[target]
        if candidate.exists():
            return candidate
    return None


def firestore_for(target: Target, key: Optional[Path]) -> tuple[Any, str]:
    """A client for ``target``'s Firebase project, and how it authenticates.

    Refuses a key file that belongs to another project: the project the data
    goes to must be the one the confirmation named.
    """
    from google.cloud.firestore import Client  # noqa: PLC0415

    project = FIREBASE_PROJECTS[target]
    if key is None:
        return Client(project=project), "gcloud application-default credentials"
    from google.oauth2 import service_account  # noqa: PLC0415

    info = json.loads(key.read_text(encoding="utf-8"))
    if info.get("project_id") != project:
        raise SystemExit(
            f"{key} belongs to project {info.get('project_id')!r}, not {project!r}."
        )
    creds = service_account.Credentials.from_service_account_info(info)
    return Client(project=project, credentials=creds), f"key file {key}"


@dataclass
class DayStatus:
    day: date
    items: int
    to_build: int


@dataclass
class ParliamentPlan:
    parliament: Parliament
    window: Optional[tuple[Any, Any]]
    days: list[DayStatus] = field(default_factory=list)

    @property
    def to_build(self) -> int:
        return sum(d.to_build for d in self.days)


def plan_parliament(
    qdrant: QdrantClient,
    parliament: Parliament,
    days: int,
    stored_hashes: dict[str, Optional[str]],
    since: Optional[date] = None,
) -> ParliamentPlan:
    """The window's days and how many of their items are not yet stored as
    they would be built now.

    Uses the same input hashes as the builder, so an item counted as stored
    here is skipped by the run without an LLM call.
    """
    sources = load_sources(qdrant, parliament, days, since=since)
    if sources is None:
        return ParliamentPlan(parliament, None)
    plan = ParliamentPlan(parliament, sources.window)
    for day in plan_days(parliament, sources.votes, sources.sitting_days):
        units = [(u.item_id, u.input_hash) for u in day.debates] + [
            (u.item_id, u.input_hash) for u in day.votes
        ]
        plan.days.append(
            DayStatus(
                day.day,
                len(units),
                sum(1 for item_id, h in units if stored_hashes.get(item_id) != h),
            )
        )
    return plan


def _week(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def format_plan(plan: ParliamentPlan) -> list[str]:
    name = f"{plan.parliament.id:>10}"
    if plan.window is None:
        return [f"{name}  no corpus data"]
    start, end = plan.window
    items = sum(d.items for d in plan.days)
    lines = [
        f"{name}  {start}..{end}  days={len(plan.days)} items={items} "
        f"stored={items - plan.to_build} to_build={plan.to_build}"
    ]
    weeks: dict[str, Counter[str]] = {}
    for day in plan.days:
        counts = weeks.setdefault(_week(day.day), Counter())
        counts["stored"] += day.items - day.to_build
        counts["to_build"] += day.to_build
    for week in sorted(weeks):
        counts = weeks[week]
        lines.append(
            f"{'':>10}    {week}  stored={counts['stored']} "
            f"to_build={counts['to_build']}"
        )
    return lines


def coverage_lines(items: list[FeedItem], parliament_id: str) -> list[str]:
    """What the store holds now: days, published items, items still German-only."""
    published = [i for i in items if i.status == "published"]
    days = {i.date for i in published}
    untranslated = sum(1 for i in published if needs_translation(i, "en"))
    return [
        f"{parliament_id:>10}  days={len(days)} items={len(published)} "
        f"without_english={untranslated}"
    ]


def _confirm(target: Target, assume_yes: bool, confirm_project: Optional[str]) -> bool:
    project = FIREBASE_PROJECTS[target]
    if target == "prod":
        if confirm_project is not None:
            return confirm_project == project
        answer = input(f"Type the project id ({project}) to write the prod feed: ")
        return answer.strip() == project
    if assume_yes:
        return True
    return input(f"Write the feed of {project}? [y/N] ").strip().lower() == "y"


def _incomplete(runs: list[tuple[ParliamentRun, Any]]) -> int:
    return sum(run.incomplete + run.deferred for run, _ in runs)


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Backfill the parliament feed of a deployed environment."
    )
    parser.add_argument("--env", required=True, choices=sorted(FIREBASE_PROJECTS))
    parser.add_argument(
        "--weeks", type=int, default=8, help="How far back to build (default: 8)"
    )
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Build from this day on instead of --weeks",
    )
    parser.add_argument(
        "--parliament",
        action="append",
        choices=sorted(PARLIAMENTS),
        help="Limit to one parliament (repeatable; default: those in the feed)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="List the days per week and what is missing; no LLM calls, no writes",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        help="Admin-SDK key file (default: the usual file in ingestion/ or ai-backend/)",
    )
    parser.add_argument("--yes", action="store_true", help="Skip the dev prompt")
    parser.add_argument(
        "--confirm-project",
        metavar="PROJECT_ID",
        help="Non-interactive prod confirmation: the prod project id",
    )
    args = parser.parse_args(argv)
    target: Target = args.env
    days = args.weeks * 7

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    problems = check_target(target, qdrant_url)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 2

    # The project is chosen explicitly below; an emulator host left in the
    # shell would silently redirect every read and write.
    guard_firestore_target("the feed backfill", allow_remote=True)
    db, auth = firestore_for(target, key_file(target, args.credentials))
    qdrant = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY") or None)
    check_fingerprint(qdrant, COLLECTION_NAME)

    parliaments = [PARLIAMENTS[p] for p in (args.parliament or FEED_PARLIAMENTS)]
    window = f"{args.since} up to" if args.since else f"{args.weeks} weeks, ending on"
    print(
        f"Target     {target}: Firestore {FIREBASE_PROJECTS[target]} ({auth})\n"
        f"Qdrant     {urlparse(qdrant_url).hostname}: {COLLECTION_NAME} -> "
        f"{FEED_COLLECTION_NAME}\n"
        f"Window     {window} each parliament's latest corpus day\n"
    )
    plans = []
    for parliament in parliaments:
        since = args.since or date.today() - timedelta(days=days)
        stored = {
            i.id: (i.input_hash if i.status == "published" else None)
            for i in read_items_since(db, parliament.id, since)
        }
        plans.append(plan_parliament(qdrant, parliament, days, stored, args.since))
    for plan in plans:
        print("\n".join(format_plan(plan)))
    to_build = sum(plan.to_build for plan in plans)
    print(f"\n{to_build} day(s) to build.")

    if args.plan or to_build == 0:
        return 0
    if not _confirm(target, args.yes, args.confirm_project):
        print("Not confirmed; nothing written.")
        return 1

    setup_feed_collection(qdrant)
    builder = FeedBuilder()
    try:
        runs = build_and_publish(
            qdrant, db, builder, parliaments, days=days, env=target, since=args.since
        )
    finally:
        builder.close()

    print("\nStored now:")
    for plan in plans:
        if plan.window is not None:
            items = read_items_since(db, plan.parliament.id, plan.window[0])
            print("\n".join(coverage_lines(items, plan.parliament.id)))
    incomplete = _incomplete(runs)
    if incomplete:
        print(
            f"\n{incomplete} item(s) are incomplete (a model call failed, a "
            "position could not be verified, or a protocol is not out yet); "
            "run the same command again to retry them."
        )
        return 3
    return 0


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # Skip interpreter teardown: after any Gemini call a native extension
    # segfaults while being finalized (see feed.bulk).
    os._exit(exit_code)
