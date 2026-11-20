# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The procedures job: sync from DIP, Drucksachen, links, feed, report.

    python -m ingestion.procedures.bulk --backfill          # first run
    python -m ingestion.procedures.bulk                     # changes since the last run
    python -m ingestion.procedures.bulk --report            # coverage only

The collection and its payload indexes come from ``ingestion.setup_collection``
(the job entrypoint and ``make run-procedures`` run it first).

A run, in order: sync procedures (backfill or DIP delta) → Drucksache text →
link votes and speeches without a link → topics of moved procedures →
feed items → ``has_links`` flags → coverage report. It runs after speech and
vote ingestion, which it links, and before the feed build, which shows it.

What a synced change needs from the later steps is saved with it
(``store.PendingStep``) and cleared only when that step succeeded, so a run
that fails or is stopped part-way leaves the rest to the next run.
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time.
if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable
from datetime import date, timedelta
from functools import partial
from typing import Any, Optional

from qdrant_client import QdrantClient

from ingestion.connectors.bundestag_speeches.client import DipClient
from ingestion.connectors.bundestag_speeches.connector import _require_dip_key
from ingestion.firestore_guard import guard_firestore_target
from ingestion.procedures.dip import DipReader, LiveDip
from ingestion.procedures.drucksachen import (
    CHUNK_RULES,
    ingest_drucksachen,
    stored_drucksachen,
    wanted_numbers,
)
from ingestion.procedures.feed_links import FirestoreProcedures, link_feed_items
from ingestion.procedures.link_apply import Linker, linked_procedure_ids
from ingestion.procedures.pdf_pages import PdfSource
from ingestion.procedures.report import collect, render, scroll_linkable
from ingestion.procedures.step_summaries import Call, summarise_procedures
from ingestion.procedures.store import PENDING_STEPS, ProcedureStore
from ingestion.procedures.sync import SyncReport, follow_up, run_sync, sync_ids
from ingestion.setup_collection import COLLECTION_NAME, check_fingerprint
from wahlchat_common.procedures import ProcedureRecord

logger = logging.getLogger(__name__)

WAHLPERIODEN = [20, 21]

_SUMMARY_LOOKBACK_DAYS = 7


def known_empty(state: dict) -> set[str]:
    """Drucksachen found to have no chunk under the current rules."""
    if state.get("drucksachen_chunk_rules") != CHUNK_RULES:
        return set()
    return set(state.get("drucksachen_without_chunks") or [])


def run(
    *,
    dip: DipReader,
    db: Any,
    qdrant: QdrantClient,
    collection: str,
    embed: Any,
    wahlperioden: list[int],
    backfill: bool,
    link: bool,
    sync: bool,
    feed: bool,
    today: date,
    summary_call: Optional[Call] = None,
    dry_run: bool = False,
    pdfs: Optional[PdfSource] = None,
    revalidate: Optional[Callable[[], None]] = None,
) -> int:
    """One job run; returns the process exit code (1 when anything failed).

    ``revalidate`` clears the web's feed cache once feed items were updated:
    the feed build that follows finds them already up to date, so it would
    not clear it for these changes.
    """
    store = ProcedureStore(db)
    report = SyncReport()
    failed = False
    if sync:
        report = run_sync(
            dip=dip,
            store=store,
            qdrant=qdrant,
            collection=collection,
            embed=embed,
            wahlperioden=wahlperioden,
            backfill=backfill,
            today=today,
            dry_run=dry_run,
            pdfs=pdfs,
        )
        print(
            f"procedures: seen={report.seen} in_scope={report.in_scope} written={report.written} "
            f"unchanged={report.unchanged} new_stage={len(report.new_stage)} failed={len(report.failed)}"
        )
        failed |= bool(report.failed)

    procedures = store.all()
    # This run's changes plus those an earlier run synced but did not follow
    # up; a dry run saved none of its own.
    work = follow_up(report)
    for step in PENDING_STEPS:
        work[step] |= store.pending(step)

    def read_drucksachen(
        of: dict[str, ProcedureRecord],
        *,
        reread: bool,
        on_batch: Optional[Callable[[list[str], set[str]], None]] = None,
    ) -> set[str]:
        """Read the procedures' Drucksachen: all of them, or only those not
        stored yet (nor known to have no text worth a chunk). Returns the
        numbers that could not be read."""
        numbers = wanted_numbers(of)
        if not reread:
            numbers -= stored_drucksachen(qdrant, collection) | known_empty(
                store.sync_state()
            )
        result = ingest_drucksachen(
            numbers,
            dip=dip,
            qdrant=qdrant,
            collection=collection,
            embed=embed,
            procedures=procedures,
            today=today,
            pdfs=pdfs,
            on_batch=on_batch,
        )
        print(
            f"drucksachen: documents={result.documents} chunks={result.chunks} "
            f"written={result.written} unchanged={result.skipped} failed={len(result.failed)}"
        )
        current = store.sync_state()
        if result.empty or current.get("drucksachen_chunk_rules") != CHUNK_RULES:
            known = known_empty(current) | set(result.empty)
            store.set_sync_state(
                {
                    **current,
                    "drucksachen_without_chunks": sorted(known),
                    "drucksachen_chunk_rules": CHUNK_RULES,
                }
            )
        return set(result.failed)

    if not dry_run:
        # New procedures' Drucksachen and those of moved ones are (re-)read: a
        # stored Drucksache may now belong to one more procedure.
        due = work["pending_drucksachen"]
        moved = {v: procedures[v] for v in due if v in procedures}
        unread = read_drucksachen(
            moved,
            reread=True,
            on_batch=_clear_as_read(
                moved, lambda done: store.clear_pending("pending_drucksachen", done)
            ),
        )
        unread_new = read_drucksachen(procedures, reread=False)
        failed |= bool(unread or unread_new)
        # An id with no stored record has nothing to read: a failed sync
        # stores and marks it again.
        store.clear_pending(
            "pending_drucksachen", (due - set(moved)) | _read_through(moved, unread)
        )

    if link:

        def add_procedures(ids: set[str]) -> dict[str, ProcedureRecord]:
            added = sync_ids(
                ids,
                dip=dip,
                store=store,
                qdrant=qdrant,
                collection=collection,
                embed=embed,
                today=today,
                dry_run=dry_run,
                pdfs=pdfs,
            )
            if added.failed:
                raise RuntimeError(f"Vorgänge {added.failed} could not be synced")
            return store.get(ids)

        linker = Linker(
            dip=dip,
            qdrant=qdrant,
            collection=collection,
            procedures=procedures,
            today=today,
            add_procedures=add_procedures,
            dry_run=dry_run,
        )
        linker.link_votes(wahlperioden)
        linker.link_speeches(wahlperioden)
        retopic = work["pending_sachgebiete"]
        failures = len(linker.report.failed)
        linker.refresh_sachgebiete(retopic)
        if not dry_run and len(linker.report.failed) == failures:
            store.clear_pending("pending_sachgebiete", retopic)
        methods = ", ".join(f"{m}={n}" for m, n in linker.report.methods.most_common())
        print(
            f"links: chunks={linker.report.chunks_written} failed={len(linker.report.failed)} [{methods}]"
        )
        failed |= bool(linker.report.failed)
        procedures = store.all()
        created = {v: procedures[v] for v in linker.report.created if v in procedures}
        if created and not dry_run:
            unread = read_drucksachen(created, reread=True)
            failed |= bool(unread)
            store.clear_pending("pending_drucksachen", _read_through(created, unread))

    summarised: set[str] = set()
    if summary_call is not None and not dry_run:
        in_feed = _feed_procedure_ids(db)
        # A law the feed links for the first time had a stage within the
        # lookback, so it has its summaries by then.
        recent = today - timedelta(days=_SUMMARY_LOOKBACK_DAYS)
        summaries = asyncio.run(
            summarise_procedures(
                {
                    v: r
                    for v, r in procedures.items()
                    if v in in_feed
                    or (r.stage_changed_on is not None and r.stage_changed_on >= recent)
                },
                qdrant=qdrant,
                collection=collection,
                call=summary_call,
                today=today,
                write=store.set_step_summaries,
            )
        )
        print(
            f"step summaries: written={len(summaries.written)} "
            f"rejected={len(summaries.rejected)} failed={len(summaries.failed)}"
        )
        failed |= bool(summaries.failed)
        # Every summarised law, not only this run's: a run that stopped
        # before the feed refresh leaves items behind their procedure.
        summarised = summaries.procedures | {
            v for v, r in procedures.items() if v in in_feed and r.step_summaries
        }

    if feed:
        lookup = FirestoreProcedures(db)
        moved_on = work["pending_feed"]
        only = None if backfill else moved_on | summarised
        if only is None or only:
            n = link_feed_items(
                db, qdrant, collection, lookup=lookup, only_ids=only, dry_run=dry_run
            )
            print(f"feed items: updated={n}")
            if not dry_run:
                store.clear_pending("pending_feed", moved_on)
                if n and revalidate is not None:
                    try:
                        revalidate()
                    except Exception:  # noqa: BLE001 — the items are written; the cache expires on its own
                        logger.exception("Clearing the web's feed cache failed")
                        failed = True

    if not dry_run:
        linked = linked_procedure_ids(qdrant, collection) | _feed_procedure_ids(db)
        flags = {
            vid: vid in linked
            for vid, record in procedures.items()
            if record.has_links != (vid in linked)
        }
        store.set_has_links(flags)
        for vid, value in flags.items():
            procedures[vid] = procedures[vid].model_copy(update={"has_links": value})

    print(
        render(collect(scroll_linkable(qdrant, collection, wahlperioden), procedures))
    )
    return 1 if failed else 0


def _publication_call() -> Call:
    from ingestion.feed.publication_llms import (  # noqa: PLC0415 (needs the model env)
        structured_output_from_publication_llms,
    )

    return structured_output_from_publication_llms


def _clear_as_read(
    of: dict[str, ProcedureRecord], clear: Callable[[set[str]], None]
) -> Callable[[list[str], set[str]], None]:
    """A batch callback that clears each procedure once the last of its
    Drucksachen is written, so a run stopped mid-step resumes there instead
    of reading every document again. A procedure with a failed document stays
    pending."""
    left = {vid: wanted_numbers({vid: record}) for vid, record in of.items()}
    owners: dict[str, set[str]] = {}
    for vid, numbers in left.items():
        for number in numbers:
            owners.setdefault(number, set()).add(vid)
    failed_in: set[str] = set()

    def on_batch(batch: list[str], failed: set[str]) -> None:
        done: set[str] = set()
        for number in batch:
            for vid in owners.get(number, ()):
                if number in failed:
                    failed_in.add(vid)
                left[vid].discard(number)
                if not left[vid] and vid not in failed_in:
                    done.add(vid)
        if done:
            clear(done)

    return on_batch


def _read_through(of: dict[str, ProcedureRecord], unread: set[str]) -> set[str]:
    """The procedures none of whose Drucksachen are among ``unread``."""
    return {
        vid for vid, record in of.items() if not wanted_numbers({vid: record}) & unread
    }


def _feed_procedure_ids(db: Any) -> set[str]:
    return {
        vid
        for snapshot in db.collection("feed_items")
        .where("parliament", "==", "bundestag")
        .stream()
        for vid in (snapshot.to_dict() or {}).get("procedure_ids") or []
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--wahlperiode", type=int, nargs="+", default=WAHLPERIODEN)
    parser.add_argument(
        "--backfill", action="store_true", help="sync every in-scope Vorgang"
    )
    parser.add_argument("--link-only", action="store_true", help="skip the DIP sync")
    parser.add_argument(
        "--no-link", action="store_true", help="skip linking votes and speeches"
    )
    parser.add_argument(
        "--no-feed", action="store_true", help="leave feed items as they are"
    )
    parser.add_argument(
        "--no-summaries", action="store_true", help="write no step summaries"
    )
    parser.add_argument(
        "--report", action="store_true", help="print the coverage report only"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="read only; write nothing"
    )
    parser.add_argument(
        "--allow-remote", action="store_true", help="write a deployed dev Firestore"
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="clear the web's feed cache after feed items changed (needs REVALIDATE_SECRET)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    guard_firestore_target("Procedures job", allow_remote=args.allow_remote)
    from ingestion.firestore_client import firestore_client  # noqa: PLC0415 — after the guard

    db = firestore_client()
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        # The link sweep scans every Bundestag speech for a missing stamp;
        # right after large writes Qdrant is still optimizing and slow to answer.
        timeout=120,
    )
    check_fingerprint(qdrant, COLLECTION_NAME)
    if args.report:
        print(
            render(
                collect(
                    scroll_linkable(qdrant, COLLECTION_NAME, args.wahlperiode),
                    ProcedureStore(db).all(),
                )
            )
        )
        return 0
    from wahlchat_common.embeddings import get_embeddings  # noqa: PLC0415

    revalidate: Optional[Callable[[], None]] = None
    if args.revalidate:
        from ingestion.feed.bulk import post_revalidate  # noqa: PLC0415

        revalidate = partial(post_revalidate, os.getenv("ENV", "dev"))

    return run(
        dip=LiveDip(DipClient(_require_dip_key())),
        db=db,
        qdrant=qdrant,
        collection=COLLECTION_NAME,
        embed=get_embeddings(task_type="RETRIEVAL_DOCUMENT"),
        wahlperioden=args.wahlperiode,
        backfill=args.backfill,
        link=not args.no_link,
        sync=not args.link_only,
        feed=not args.no_feed,
        summary_call=None if args.no_summaries else _publication_call(),
        today=date.today(),
        dry_run=args.dry_run,
        # Not cached: each PDF is read once per run, and a Cloud Run job's
        # disk is its memory.
        pdfs=PdfSource(),
        revalidate=revalidate,
    )


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.exit(exit_code)
