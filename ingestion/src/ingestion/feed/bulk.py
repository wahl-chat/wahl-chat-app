# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Build the parliament feed from the corpus and publish it.

Per parliament, the window ends on the latest day the corpus has data for (not
today — ingestion lags) and spans ``--days``. The source defines the items: one
per agenda item with speeches, one per poll. Each carries the hash of its own
inputs, so a rerun regenerates only the items whose sources changed; an
unchanged day costs no LLM call. The scheduled job runs weekly after the
speech and vote jobs, several times in a row: ``--time-budget`` stops it
starting new items before the job's time cap, and the next run picks up what
is still missing.

Each built day is published before the next one starts: translated, indexed
in the feed collection in Qdrant, then written to Firestore ``feed_items`` and
``feed_editions``. Qdrant goes first, so a crash leaves at worst an indexed item
Firestore does not have yet; the next run rewrites both.

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 \
        uv run python -m ingestion.feed.bulk --days 14 --dry-run --out /tmp/feed.json
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time. override=False keeps exported
# variables (make, CI, the job spec) in force; Cloud Run has no .env.
if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import json
import logging
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from qdrant_client import QdrantClient

from ingestion.feed.builder import DayPlan, FeedBuilder, build_day, plan_days
from ingestion.feed.index import FEED_COLLECTION_NAME, IndexReport, index_items
from ingestion.feed.items import assemble_edition
from ingestion.feed.models import FeedEdition, FeedItem
from ingestion.feed.parliaments import (
    FEED_PARLIAMENTS,
    PARLIAMENTS,
    Parliament,
    load_party_display,
)
from ingestion.feed.protocol_pages import apply_protocols
from ingestion.feed.reader import (
    SPEECH_SOURCE_TYPE,
    VOTE_SOURCE_TYPE,
    SittingDay,
    assemble_speeches,
    compute_window,
    group_sitting_days,
    latest_publish_date,
    scroll_payloads,
    window_filter,
)
from ingestion.feed.store import (
    carry_over_translations,
    read_edition_item_ids,
    read_items_since,
    vanished_item_ids,
    write_feed,
)
from ingestion.feed.translate import (
    TranslationReport,
    needs_translation,
    translate_items,
)
from ingestion.firestore_guard import guard_firestore_target
from ingestion.setup_collection import COLLECTION_NAME, check_fingerprint

logger = logging.getLogger(__name__)

# Must match CacheTags.FEED in web/lib/cache-tags.ts.
FEED_CACHE_TAG = "feed"
_DEFAULT_SITE_URLS = {"prod": "https://wahl.chat", "dev": "https://dev.wahl.chat"}
# No new item starts once --time-budget is spent; calls already running get
# this long to finish before they are cut, leaving the rest of the job's cap
# for translation fallbacks and the writes.
_CALL_GRACE_S = 75


@dataclass
class ParliamentRun:
    parliament: Parliament
    window: Optional[tuple[date, date]]
    days_built: int = 0
    unchanged: int = 0
    items_built: int = 0
    # Built, but retried next run: a fallback, or a Fraktion without a position.
    incomplete: int = 0
    # Debates whose protocol could not be read yet, so their order is unknown.
    deferred: int = 0
    out_of_time: bool = False


@dataclass
class DayBuild:
    """One day ready to publish: its edition, every item the edition lists
    (``changed`` marks which need writing), and the ids to retract."""

    edition: FeedEdition
    items: list[FeedItem]
    changed: set[str]
    built: set[str]
    retracted_ids: list[str] = field(default_factory=list)


@dataclass
class Published:
    editions: list[FeedEdition] = field(default_factory=list)
    items: list[FeedItem] = field(default_factory=list)
    retracted: int = 0
    translation: TranslationReport = field(default_factory=TranslationReport)
    index: IndexReport = field(default_factory=IndexReport)
    translations_kept: int = 0

    def add(self, other: Published) -> None:
        self.editions.extend(other.editions)
        self.items.extend(other.items)
        self.retracted += other.retracted
        self.translation.translated += other.translation.translated
        self.translation.failed += other.translation.failed
        self.translation.dropped_stale += other.translation.dropped_stale
        self.index.upserted += other.index.upserted
        self.index.unchanged += other.index.unchanged
        self.index.deleted += other.index.deleted
        self.translations_kept += other.translations_kept


def parliament_window(
    qdrant: QdrantClient,
    parliament: Parliament,
    days: int,
    since: Optional[date] = None,
) -> Optional[tuple[date, date]]:
    """``days`` ending on the latest corpus day, or ``since`` up to it."""
    source_types = [VOTE_SOURCE_TYPE] + (
        [SPEECH_SOURCE_TYPE] if parliament.has_speeches else []
    )
    latest = latest_publish_date(
        qdrant, COLLECTION_NAME, source_types, parliament.region
    )
    if latest is None:
        logger.warning("No corpus data for %s (%s)", parliament.id, parliament.region)
        return None
    if since is not None:
        return since, max(since, latest)
    return compute_window(latest, days)


@dataclass
class WindowSources:
    window: tuple[date, date]
    votes: list[dict]
    sitting_days: dict[date, SittingDay]


def load_sources(
    qdrant: QdrantClient,
    parliament: Parliament,
    days: int,
    *,
    since: Optional[date] = None,
) -> Optional[WindowSources]:
    """The window's vote payloads and sitting days, or None without corpus data.

    Sitting days come with the Bundestag's protocol applied (see
    ``protocol_pages``): speeches in order, twins from the other source
    dropped. Only that state is ever built or hashed.
    """
    window = parliament_window(qdrant, parliament, days, since)
    if window is None:
        return None
    start, end = window
    votes = scroll_payloads(
        qdrant,
        COLLECTION_NAME,
        window_filter(VOTE_SOURCE_TYPE, parliament.region, start, end),
    )
    sitting_days: dict[date, SittingDay] = {}
    if parliament.has_speeches:
        # A day earlier, so a sitting that began the day before the window
        # and ran past midnight is still dated by its first speech.
        speech_payloads = scroll_payloads(
            qdrant,
            COLLECTION_NAME,
            window_filter(
                SPEECH_SOURCE_TYPE,
                parliament.region,
                start - timedelta(days=1),
                end,
            ),
        )
        sitting_days = {
            day: sitting
            for day, sitting in group_sitting_days(
                assemble_speeches(speech_payloads)
            ).items()
            if day >= start
        }
        for sitting in sitting_days.values():
            ordered = apply_protocols(sitting)
            logger.info(
                "%s: %d of %d agenda items in protocol order",
                sitting.day,
                ordered,
                len(sitting.agenda_items),
            )
    return WindowSources(window, votes, sitting_days)


def _is_current(stored: Optional[FeedItem], input_hash: str) -> bool:
    return (
        stored is not None
        and stored.status == "published"
        and stored.input_hash == input_hash
    )


def plan_day(
    builder: FeedBuilder,
    parliament: Parliament,
    plan: DayPlan,
    display: dict[str, Any],
    *,
    stored: dict[str, FeedItem],
    stored_edition_ids: Optional[list[str]],
    force: bool,
    run: ParliamentRun,
    out_of_time: Callable[[], bool],
    now: datetime,
) -> Optional[DayBuild]:
    """Generate what changed in one day and assemble its edition; None when
    the day is unchanged and fully translated."""
    debates = [
        u
        for u in plan.debates
        if force or not _is_current(stored.get(u.item_id), u.input_hash)
    ]
    votes = [
        u
        for u in plan.votes
        if force or not _is_current(stored.get(u.item_id), u.input_hash)
    ]
    run.deferred += sum(1 for u in debates if not u.buildable)
    built_items = (
        build_day(
            builder,
            parliament,
            plan,
            debates,
            votes,
            display,
            now=now,
            out_of_time=out_of_time,
        )
        if any(u.buildable for u in debates) or votes
        else []
    )
    built = {i.id: i for i in built_items}

    listed: list[FeedItem] = []
    for item_id in plan.item_ids:
        # A unit that could not be rebuilt keeps its stored version; one never
        # built yet stays out until a run builds it.
        item = built.get(item_id) or stored.get(item_id)
        if item is not None and item.status == "published":
            listed.append(item)
    edition, ranked = assemble_edition(
        parliament, plan.edition_id, plan.day, plan.protocols, listed, now
    )
    retracted = vanished_item_ids(stored_edition_ids or [], edition.item_ids)
    changed = {
        i.id
        for i in ranked
        if i.id in built or stored.get(i.id) is None or stored[i.id].rank != i.rank
    }
    untranslated = any(needs_translation(i, "en") for i in ranked)
    if (
        not changed
        and not retracted
        and stored_edition_ids == edition.item_ids
        and not untranslated
    ):
        return None
    run.items_built += len(built)
    run.incomplete += sum(1 for i in built.values() if i.input_hash is None)
    return DayBuild(
        edition=edition,
        items=ranked,
        changed=changed,
        built=set(built),
        retracted_ids=retracted,
    )


def build_for_parliament(
    qdrant: QdrantClient,
    parliament: Parliament,
    builder: FeedBuilder,
    *,
    days: int,
    env: str,
    db: Any,
    force: bool,
    publish_day: Callable[[DayBuild, dict[str, FeedItem]], None],
    since: Optional[date] = None,
    out_of_time: Callable[[], bool] = lambda: False,
    now: Optional[datetime] = None,
) -> ParliamentRun:
    """Build the window's days newest first, publishing each one as it is built.

    Stops between items once ``out_of_time()`` says so; whatever is published
    is stored, so the next run skips it.
    """
    sources = load_sources(qdrant, parliament, days, since=since)
    if sources is None:
        return ParliamentRun(parliament, None)
    run = ParliamentRun(parliament, sources.window)
    plans = plan_days(parliament, sources.votes, sources.sitting_days)
    stored = (
        {i.id: i for i in read_items_since(db, parliament.id, sources.window[0])}
        if db is not None
        else {}
    )
    stored_editions = (
        read_edition_item_ids(db, [p.edition_id for p in plans]) if db else {}
    )
    display = load_party_display(parliament, env)
    for plan in plans:
        if out_of_time():
            run.out_of_time = True
            break
        day = plan_day(
            builder,
            parliament,
            plan,
            display,
            stored=stored,
            stored_edition_ids=stored_editions.get(plan.edition_id),
            force=force,
            run=run,
            out_of_time=out_of_time,
            now=now or datetime.now(timezone.utc),
        )
        if day is None:
            run.unchanged += 1
            continue
        run.days_built += 1
        publish_day(day, stored)
    if out_of_time():
        run.out_of_time = True
    return run


def publish(
    day: DayBuild,
    stored: dict[str, FeedItem],
    *,
    db: Any,
    builder: FeedBuilder,
    qdrant: Optional[QdrantClient],
    embed: Any,
    translate: bool,
) -> Published:
    """Translate, index and store one built day.

    ``db=None`` is a dry run: nothing is written. ``qdrant=None`` skips the
    index.
    """
    out = Published(editions=[day.edition], retracted=len(day.retracted_ids))
    built = [i for i in day.items if i.id in day.built]
    out.translations_kept = carry_over_translations(built, stored)
    to_write = {i.id for i in day.items if i.id in day.changed}
    if translate:
        pending = [i for i in day.items if needs_translation(i, "en")]
        out.translation = translate_items(pending, builder)
        to_write |= {i.id for i in pending}
    out.items = [i for i in day.items if i.id in to_write]
    if qdrant is not None:
        out.index = index_items(qdrant, embed, built, retracted_ids=day.retracted_ids)
    if db is not None:
        write_feed(db, [day.edition], out.items, day.retracted_ids)
    return out


def backfill_translations(
    db: Any,
    qdrant: QdrantClient,
    builder: FeedBuilder,
    parliaments: list[Parliament],
    days: int,
) -> TranslationReport:
    """Translate stored items whose translation is missing or stale."""
    total = TranslationReport()
    for parliament in parliaments:
        window = parliament_window(qdrant, parliament, days)
        if window is None:
            continue
        items = read_items_since(db, parliament.id, window[0])
        report = translate_items(items, builder)
        total.translated += report.translated
        total.failed += report.failed
        total.dropped_stale += report.dropped_stale
        if report.translated or report.dropped_stale:
            write_feed(db, [], items)
    return total


def _firestore_client() -> Any:
    """The Firestore the feed goes to. Call only after the target guard.

    Against the emulator this is an anonymous client for the project the web
    reads (``GOOGLE_CLOUD_PROJECT``, default ``demo-wahl-chat`` like the
    Makefile's EMULATOR_PROJECT). The shared client would instead take the
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
    from ingestion.firestore_client import firestore_client  # noqa: PLC0415

    return firestore_client()


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
        json={"tags": [FEED_CACHE_TAG]},
        headers={"Authorization": f"Bearer {secret}"},
        timeout=30,
    )
    response.raise_for_status()
    print(f"revalidated {FEED_CACHE_TAG} on {base}")


def _summary_line(run: ParliamentRun, published: Published) -> str:
    window = f"{run.window[0]}..{run.window[1]}" if run.window else "no data"
    t = published.translation
    return (
        f"{run.parliament.id:>10}  window={window}  days_built={run.days_built} "
        f"unchanged={run.unchanged} items_built={run.items_built} "
        f"items_written={len(published.items)} retracted={published.retracted} "
        f"incomplete={run.incomplete} deferred={run.deferred} "
        f"translated={t.translated} translation_failed={t.failed} "
        f"translations_kept={published.translations_kept} "
        f"indexed={published.index.upserted}"
        + ("  stopped: time budget spent" if run.out_of_time else "")
    )


def build_and_publish(
    qdrant: QdrantClient,
    db: Any,
    builder: FeedBuilder,
    parliaments: list[Parliament],
    *,
    days: int,
    env: str,
    since: Optional[date] = None,
    force: bool = False,
    translate: bool = True,
    index: bool = True,
    out_of_time: Callable[[], bool] = lambda: False,
) -> list[tuple[ParliamentRun, Published]]:
    """Every parliament's window, day by day; prints one summary line each.

    ``db=None`` is a dry run (nothing read back or written).
    """
    index_to = qdrant if index and db is not None else None
    embed = _embeddings() if index_to is not None else None
    runs: list[tuple[ParliamentRun, Published]] = []
    for parliament in parliaments:
        if out_of_time():
            print(f"{parliament.id:>10}  skipped: time budget spent")
            continue
        published = Published()

        def publish_day(
            day: DayBuild, stored: dict[str, FeedItem], into: Published = published
        ) -> None:
            into.add(
                publish(
                    day,
                    stored,
                    db=db,
                    builder=builder,
                    qdrant=index_to,
                    embed=embed,
                    translate=translate,
                )
            )

        run = build_for_parliament(
            qdrant,
            parliament,
            builder,
            days=days,
            env=env,
            db=db,
            since=since,
            force=force,
            publish_day=publish_day,
            out_of_time=out_of_time,
        )
        runs.append((run, published))
        print(_summary_line(run, published))
    return runs


def _embeddings() -> Any:
    from wahlchat_common.embeddings import get_embeddings  # noqa: PLC0415

    return get_embeddings(task_type="RETRIEVAL_DOCUMENT")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Build and publish the parliament feed."
    )
    parser.add_argument(
        "--days", type=int, default=14, help="Window length in days (default: 14)"
    )
    parser.add_argument(
        "--parliament",
        action="append",
        choices=sorted(PARLIAMENTS),
        help="Limit to one parliament (repeatable; default: those in the feed)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Rebuild unchanged days too"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build (incl. LLM calls) but write neither Firestore nor Qdrant; combine with --out",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="Also write the editions and items as JSON to this file",
    )
    parser.add_argument(
        "--skip-translate", action="store_true", help="Publish German only"
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help=f"Do not write the semantic index ({FEED_COLLECTION_NAME})",
    )
    parser.add_argument(
        "--translate-backfill",
        action="store_true",
        help="Only translate stored items in the window whose translation is missing or stale",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit writes to non-emulator Firestore when ENV != prod",
    )
    parser.add_argument(
        "--time-budget",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Wall-clock budget; no new item starts once it is spent",
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Bust the web cache tag afterwards (needs REVALIDATE_SECRET)",
    )
    args = parser.parse_args(argv)

    started = time.monotonic()

    def out_of_time() -> bool:
        return (
            args.time_budget is not None
            and time.monotonic() - started >= args.time_budget
        )

    env = os.getenv("ENV", "dev")
    parliaments = [PARLIAMENTS[p] for p in (args.parliament or FEED_PARLIAMENTS)]

    db = None
    if not args.dry_run:
        guard_firestore_target("the feed builder", allow_remote=args.allow_remote)
        db = _firestore_client()

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    check_fingerprint(qdrant, COLLECTION_NAME)

    builder = FeedBuilder(
        deadline=started + args.time_budget + _CALL_GRACE_S
        if args.time_budget is not None
        else None
    )
    try:
        if args.translate_backfill:
            if db is None:
                print(
                    "--translate-backfill needs Firestore; drop --dry-run.",
                    file=sys.stderr,
                )
                return 2
            report = backfill_translations(db, qdrant, builder, parliaments, args.days)
            print(
                f"translated={report.translated} failed={report.failed} "
                f"dropped_stale={report.dropped_stale}"
            )
            return 0

        runs = build_and_publish(
            qdrant,
            db,
            builder,
            parliaments,
            days=args.days,
            env=env,
            force=args.force,
            translate=not args.skip_translate,
            index=not (args.dry_run or args.skip_index),
            out_of_time=out_of_time,
        )
    finally:
        builder.close()

    if args.out:
        args.out.write_text(
            json.dumps(
                {
                    "editions": [
                        e.model_dump(mode="json") for _, p in runs for e in p.editions
                    ],
                    "items": [
                        i.model_dump(mode="json") for _, p in runs for i in p.items
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.out}")

    if db is not None and args.revalidate:
        post_revalidate(env)

    if runs and all(run.window is None for run, _ in runs):
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
