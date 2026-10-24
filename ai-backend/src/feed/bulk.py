# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Build the parliament feed from the corpus and publish it.

Per parliament, the window ends on the latest day the corpus has data for (not
today — Landtage sit irregularly and ingestion lags) and spans ``--days``.
Reruns are cheap: a day whose source payloads are unchanged since the stored
edition is skipped without LLM calls, so the job is safe to schedule daily.

Each built day is split into feed items, translated, indexed in the feed
collection in Qdrant, then written to Firestore ``feed_items`` and
``feed_editions``. Qdrant goes first, so a crash leaves at worst an indexed
item Firestore does not have yet; the next run rewrites both.

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 \
        uv run python -m src.feed.bulk --days 14 --dry-run --out /tmp/feed.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx
from qdrant_client import QdrantClient

from src.feed.builder import DigestBuilder, build_digests
from src.feed.index import FEED_COLLECTION_NAME, IndexReport, index_items
from src.feed.items import split_digest
from src.feed.models import DailyDigest, FeedEdition, FeedItem
from src.feed.parliaments import PARLIAMENTS, Parliament, load_party_display
from src.feed.protocol_pages import attach_protocol_pages
from src.feed.reader import (
    SPEECH_SOURCE_TYPE,
    VOTE_SOURCE_TYPE,
    assemble_speeches,
    compute_window,
    group_sitting_days,
    latest_publish_date,
    scroll_payloads,
    window_filter,
)
from src.feed.store import (
    carry_over_translations,
    read_edition_hashes,
    read_editions,
    read_items,
    read_items_since,
    vanished_items,
    write_feed,
)
from src.feed.translate import TranslationReport, translate_items
from src.firestore_guard import guard_firestore_target
from src.ingestion.setup_collection import COLLECTION_NAME, check_fingerprint

logger = logging.getLogger(__name__)

# Must match CacheTags.FEED in web/lib/cache-tags.ts.
FEED_CACHE_TAG = "feed"
_DEFAULT_SITE_URLS = {"prod": "https://wahl.chat", "dev": "https://dev.wahl.chat"}


@dataclass
class ParliamentRun:
    parliament: Parliament
    window: Optional[tuple[Any, Any]]
    digests: list[DailyDigest]
    unchanged: int


@dataclass
class Published:
    editions: list[FeedEdition] = field(default_factory=list)
    items: list[FeedItem] = field(default_factory=list)
    retracted: list[FeedItem] = field(default_factory=list)
    translation: TranslationReport = field(default_factory=TranslationReport)
    index: IndexReport = field(default_factory=IndexReport)
    translations_kept: int = 0


def parliament_window(
    qdrant: QdrantClient, parliament: Parliament, days: int
) -> Optional[tuple[Any, Any]]:
    source_types = [VOTE_SOURCE_TYPE] + (
        [SPEECH_SOURCE_TYPE] if parliament.has_speeches else []
    )
    latest = latest_publish_date(
        qdrant, COLLECTION_NAME, source_types, parliament.region
    )
    if latest is None:
        logger.warning("No corpus data for %s (%s)", parliament.id, parliament.region)
        return None
    return compute_window(latest, days)


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
    window = parliament_window(qdrant, parliament, days)
    if window is None:
        return ParliamentRun(parliament, None, [], 0)
    start, end = window
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
        for sitting in sitting_days.values():
            attached = attach_protocol_pages(sitting)
            logger.info(
                "%s: %d speeches linked to their protocol page", sitting.day, attached
            )

    digests, unchanged = build_digests(
        parliament,
        votes,
        sitting_days,
        load_party_display(parliament, env),
        builder,
        existing_hashes=existing_hashes,
        force=force,
    )
    return ParliamentRun(parliament, window, digests, unchanged)


def publish(
    digests: list[DailyDigest],
    *,
    db: Any,
    builder: DigestBuilder,
    qdrant: Optional[QdrantClient],
    embed: Any,
    translate: bool,
) -> Published:
    """Split, translate, index and store built days.

    ``db=None`` is a dry run: nothing is read back or written. ``qdrant=None``
    skips the index.
    """
    out = Published()
    for digest in digests:
        edition, items = split_digest(digest)
        out.editions.append(edition)
        out.items.extend(items)

    if db is not None:
        previous = read_editions(db, [e.id for e in out.editions])
        stored = read_items(
            db,
            {i.id for i in out.items}
            | {item_id for e in previous.values() for item_id in e.item_ids},
        )
        out.translations_kept = carry_over_translations(out.items, stored)
        out.retracted = vanished_items(previous, out.editions, stored)

    if translate:
        out.translation = translate_items(out.items, builder)
    if qdrant is not None:
        out.index = index_items(qdrant, embed, out.items + out.retracted)
    if db is not None:
        write_feed(db, out.editions, out.items + out.retracted)
    return out


def backfill_translations(
    db: Any,
    qdrant: QdrantClient,
    builder: DigestBuilder,
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
    incomplete = sum(1 for d in run.digests if d.input_hash is None)
    t = published.translation
    return (
        f"{run.parliament.id:>10}  window={window}  days_built={len(run.digests)} "
        f"unchanged={run.unchanged} items={len(published.items)} "
        f"retracted={len(published.retracted)} incomplete={incomplete} "
        f"translated={t.translated} translation_failed={t.failed} "
        f"translations_kept={published.translations_kept} "
        f"indexed={published.index.upserted}"
    )


def _embeddings() -> Any:
    from src.embeddings import get_embeddings  # noqa: PLC0415

    return get_embeddings(task_type="RETRIEVAL_DOCUMENT")


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
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
        help="Limit to one parliament (repeatable; default: all)",
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
        "--revalidate",
        action="store_true",
        help="Bust the web cache tag afterwards (needs REVALIDATE_SECRET)",
    )
    args = parser.parse_args(argv)

    env = os.getenv("ENV", "dev")
    parliaments = [PARLIAMENTS[p] for p in (args.parliament or sorted(PARLIAMENTS))]

    db = None
    if not args.dry_run:
        guard_firestore_target("the feed builder", allow_remote=args.allow_remote)
        db = _firestore_client()

    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    check_fingerprint(qdrant, COLLECTION_NAME)

    builder = DigestBuilder()
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

        existing = read_edition_hashes(db, [p.id for p in parliaments]) if db else {}
        index_to = None if args.dry_run or args.skip_index else qdrant
        embed = _embeddings() if index_to is not None else None
        runs: list[tuple[ParliamentRun, Published]] = []
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
            published = publish(
                run.digests,
                db=db,
                builder=builder,
                qdrant=index_to,
                embed=embed,
                translate=not args.skip_translate,
            )
            runs.append((run, published))
            print(_summary_line(run, published))
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

    if all(run.window is None for run, _ in runs):
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
