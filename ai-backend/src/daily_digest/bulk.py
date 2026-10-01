# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Build daily parliament digests from the corpus and write them to Firestore.

Per parliament, the window ends on the latest day the corpus has data for (not
today — Landtage sit irregularly and ingestion lags) and spans ``--days``.
Reruns are cheap: a day whose source payloads are unchanged since the stored
digest is skipped without LLM calls.

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 \
        uv run python -m src.daily_digest.bulk --days 14 --dry-run --out /tmp/digests.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx
from google.cloud.firestore_v1.base_query import FieldFilter
from qdrant_client import QdrantClient

from src.daily_digest.builder import DigestBuilder, build_digests
from src.daily_digest.models import DailyDigest
from src.daily_digest.parliaments import PARLIAMENTS, Parliament, load_party_display
from src.daily_digest.reader import (
    SPEECH_SOURCE_TYPE,
    VOTE_SOURCE_TYPE,
    assemble_speeches,
    compute_window,
    group_sitting_days,
    latest_publish_date,
    scroll_payloads,
    window_filter,
)
from src.firestore_guard import guard_firestore_target
from src.ingestion.setup_collection import COLLECTION_NAME, check_fingerprint

logger = logging.getLogger(__name__)

DIGEST_COLLECTION = "daily_digests"
# Must match CacheTags.DAILY_DIGESTS in web/lib/cache-tags.ts.
DIGEST_CACHE_TAG = "daily_digests"
_DEFAULT_SITE_URLS = {"prod": "https://wahl.chat", "dev": "https://dev.wahl.chat"}


@dataclass
class ParliamentRun:
    parliament: Parliament
    window: Optional[tuple[Any, Any]]
    digests: list[DailyDigest]
    unchanged: int


def build_for_parliament(
    qdrant: QdrantClient,
    parliament: Parliament,
    builder: DigestBuilder,
    *,
    days: int,
    env: str,
    existing_hashes: dict[str, Optional[str]],
    force: bool,
) -> ParliamentRun:
    source_types = [VOTE_SOURCE_TYPE] + (
        [SPEECH_SOURCE_TYPE] if parliament.has_speeches else []
    )
    latest = latest_publish_date(
        qdrant, COLLECTION_NAME, source_types, parliament.region
    )
    if latest is None:
        logger.warning("No corpus data for %s (%s)", parliament.id, parliament.region)
        return ParliamentRun(parliament, None, [], 0)

    start, end = compute_window(latest, days)
    votes = scroll_payloads(
        qdrant,
        COLLECTION_NAME,
        window_filter(VOTE_SOURCE_TYPE, parliament.region, start, end),
    )
    sitting_days = {}
    if parliament.has_speeches:
        speech_payloads = scroll_payloads(
            qdrant,
            COLLECTION_NAME,
            window_filter(SPEECH_SOURCE_TYPE, parliament.region, start, end),
        )
        sitting_days = group_sitting_days(assemble_speeches(speech_payloads))

    digests, unchanged = build_digests(
        parliament,
        votes,
        sitting_days,
        load_party_display(parliament, env),
        builder,
        existing_hashes=existing_hashes,
        force=force,
    )
    return ParliamentRun(parliament, (start, end), digests, unchanged)


def _firestore_client() -> Any:
    """The Firestore the digests go to. Call only after the target guard.

    Against the emulator this is an anonymous client for the project the web
    reads (``GOOGLE_CLOUD_PROJECT``, default ``demo-wahl-chat`` like the
    Makefile's EMULATOR_PROJECT). ``firebase_service`` would instead take the
    project from whichever admin-SDK key file sits in the working directory,
    and the emulator keeps every project apart, so the page would read an empty
    collection.
    """
    if os.getenv("FIRESTORE_EMULATOR_HOST"):
        from google.auth.credentials import AnonymousCredentials  # noqa: PLC0415
        from google.cloud import firestore  # noqa: PLC0415

        return firestore.Client(
            project=os.getenv("GOOGLE_CLOUD_PROJECT") or "demo-wahl-chat",
            credentials=AnonymousCredentials(),
        )
    # Imported lazily so firebase_admin never initializes against real
    # Firestore unless the guard allowed it.
    from src.firebase_service import db  # noqa: PLC0415

    return db


def read_existing_hashes(
    db: Any, parliament_ids: list[str]
) -> dict[str, Optional[str]]:
    hashes: dict[str, Optional[str]] = {}
    for parliament_id in parliament_ids:
        query = db.collection(DIGEST_COLLECTION).where(
            filter=FieldFilter("parliament", "==", parliament_id)
        )
        for snapshot in query.stream():
            hashes[snapshot.id] = (snapshot.to_dict() or {}).get("input_hash")
    return hashes


def write_digests(db: Any, digests: list[DailyDigest]) -> None:
    for digest in digests:
        db.collection(DIGEST_COLLECTION).document(digest.id).set(
            digest.model_dump(mode="json")
        )


def post_revalidate(env: str) -> None:
    secret = os.getenv("REVALIDATE_SECRET")
    base = (
        os.getenv("REVALIDATE_URL")
        or os.getenv("SITE_URL")
        or _DEFAULT_SITE_URLS.get(env)
    )
    if not secret or not base:
        logger.warning(
            "Skipping cache revalidation: set REVALIDATE_SECRET (and SITE_URL "
            "outside dev/prod). The web cache refreshes within 24h on its own."
        )
        return
    response = httpx.post(
        f"{base.rstrip('/')}/api/revalidate",
        json={"tags": [DIGEST_CACHE_TAG]},
        headers={"Authorization": f"Bearer {secret}"},
        timeout=30,
    )
    response.raise_for_status()
    print(f"revalidated {DIGEST_CACHE_TAG} on {base}")


def _summary_line(run: ParliamentRun) -> str:
    window = f"{run.window[0]}..{run.window[1]}" if run.window else "no data"
    votes = sum(len(d.votes) for d in run.digests)
    sessions = sum(1 for d in run.digests if d.session)
    incomplete = sum(1 for d in run.digests if d.input_hash is None)
    return (
        f"{run.parliament.id:>10}  window={window}  days_built={len(run.digests)} "
        f"unchanged={run.unchanged} votes={votes} sessions={sessions} "
        f"incomplete={incomplete}"
    )


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Build daily parliament digests.")
    parser.add_argument(
        "--days", type=int, default=14, help="Window length in days (default: 14)"
    )
    parser.add_argument(
        "--parliament",
        action="append",
        choices=sorted(PARLIAMENTS),
        help="Limit to one parliament (repeatable; default: all)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Rebuild unchanged days too"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build (incl. LLM calls) but do not write Firestore; combine with --out",
    )
    parser.add_argument(
        "--out", type=Path, help="Also write the digests as JSON to this file"
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit writes to non-emulator Firestore when ENV != prod",
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Bust the web cache tag afterwards (needs REVALIDATE_SECRET)",
    )
    args = parser.parse_args(argv)

    env = os.getenv("ENV", "dev")
    parliaments = [PARLIAMENTS[p] for p in (args.parliament or sorted(PARLIAMENTS))]

    db = None
    if not args.dry_run:
        guard_firestore_target(
            "the daily digest builder", allow_remote=args.allow_remote
        )
        db = _firestore_client()

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    check_fingerprint(qdrant, COLLECTION_NAME)

    existing = read_existing_hashes(db, [p.id for p in parliaments]) if db else {}
    builder = DigestBuilder()
    runs: list[ParliamentRun] = []
    try:
        for parliament in parliaments:
            run = build_for_parliament(
                qdrant,
                parliament,
                builder,
                days=args.days,
                env=env,
                existing_hashes=existing,
                force=args.force,
            )
            if db is not None:
                write_digests(db, run.digests)
            runs.append(run)
            print(_summary_line(run))
    finally:
        builder.close()

    if args.out:
        args.out.write_text(
            json.dumps(
                [d.model_dump(mode="json") for run in runs for d in run.digests],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.out}")

    if db is not None and args.revalidate:
        post_revalidate(env)

    if all(run.window is None for run in runs):
        print("No corpus data in any selected parliament.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # Skip interpreter teardown: after any Gemini call a native extension
    # segfaults while being finalized, turning a successful run into exit 139
    # (fatal for a scheduled job). Everything is written and flushed by now.
    os._exit(exit_code)
