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
``has_links`` flags → feed items → coverage report. It runs after speech and
vote ingestion, which it links, and before the feed build, which shows it.
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time.
if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import argparse
import logging
import os
import sys
from datetime import date
from typing import Any, Optional

from qdrant_client import QdrantClient

from ingestion.connectors.bundestag_speeches.client import DipClient
from ingestion.connectors.bundestag_speeches.connector import _require_dip_key
from ingestion.firestore_guard import guard_firestore_target
from ingestion.procedures.dip import DipReader, LiveDip
from ingestion.procedures.drucksachen import (
    ingest_drucksachen,
    stored_drucksachen,
    wanted_numbers,
)
from ingestion.procedures.feed_links import FirestoreProcedures, link_feed_items
from ingestion.procedures.link_apply import Linker, linked_procedure_ids
from ingestion.procedures.report import collect, render, scroll_linkable
from ingestion.procedures.store import ProcedureStore
from ingestion.procedures.sync import SyncReport, run_sync, sync_ids
from ingestion.setup_collection import COLLECTION_NAME, check_fingerprint
from wahlchat_common.procedures import ProcedureRecord

logger = logging.getLogger(__name__)

WAHLPERIODEN = [20, 21]
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
    dry_run: bool = False,
) -> int:
    """One job run; returns the process exit code (1 when anything failed)."""
    store = ProcedureStore(db)
    report = SyncReport()
    failed = False
    if sync:
        report = run_sync(
            dip=dip, store=store, qdrant=qdrant, collection=collection, embed=embed,
            wahlperioden=wahlperioden, backfill=backfill, today=today, dry_run=dry_run,
        )
        print(
            f"procedures: seen={report.seen} in_scope={report.in_scope} written={report.written} "
            f"unchanged={report.unchanged} new_stage={len(report.new_stage)} failed={len(report.failed)}"
        )
        failed |= bool(report.failed)

    procedures = store.all()
    # New procedures' Drucksachen and those of moved ones are (re-)read: a
    # stored Drucksache may now belong to one more procedure.
    changed = set(report.new_stage) | set(report.changed_sachgebiete) | set(report.created)

    def read_drucksachen(of: dict[str, ProcedureRecord], *, reread: bool) -> bool:
        """Read the procedures' Drucksachen: all of them, or only those not
        stored yet (nor known to have no text worth a chunk). Returns whether
        every document was read."""
        numbers = wanted_numbers(of)
        if not reread:
            known_empty = set(store.sync_state().get("drucksachen_without_chunks") or [])
            numbers -= stored_drucksachen(qdrant, collection) | known_empty
        result = ingest_drucksachen(
            numbers, dip=dip, qdrant=qdrant, collection=collection, embed=embed,
            procedures=procedures, today=today,
        )
        print(
            f"drucksachen: documents={result.documents} chunks={result.chunks} "
            f"written={result.written} unchanged={result.skipped} failed={len(result.failed)}"
        )
        if result.empty:
            current = store.sync_state()
            known = set(current.get("drucksachen_without_chunks") or []) | set(result.empty)
            store.set_sync_state({**current, "drucksachen_without_chunks": sorted(known)})
        return not result.failed

    if not dry_run:
        moved = {v: procedures[v] for v in changed if v in procedures}
        complete = read_drucksachen(moved, reread=True) & read_drucksachen(procedures, reread=False)
        failed |= not complete

    if link:
        def add_procedures(ids: set[str]) -> dict[str, ProcedureRecord]:
            added = sync_ids(ids, dip=dip, store=store, qdrant=qdrant, collection=collection,
                             embed=embed, today=today, dry_run=dry_run)
            if added.failed:
                raise RuntimeError(f"Vorgänge {added.failed} could not be synced")
            return store.get(ids)

        linker = Linker(dip=dip, qdrant=qdrant, collection=collection, procedures=procedures,
                        today=today, add_procedures=add_procedures, dry_run=dry_run)
        linker.link_votes(wahlperioden)
        linker.link_speeches(wahlperioden)
        linker.refresh_sachgebiete(report.changed_sachgebiete)
        methods = ", ".join(f"{m}={n}" for m, n in linker.report.methods.most_common())
        print(f"links: chunks={linker.report.chunks_written} failed={len(linker.report.failed)} [{methods}]")
        failed |= bool(linker.report.failed)
        procedures = store.all()
        created = {v: procedures[v] for v in linker.report.created if v in procedures}
        if created and not dry_run:
            failed |= not read_drucksachen(created, reread=True)

    if feed:
        lookup = FirestoreProcedures(db)
        only = None if backfill else set(report.new_stage)
        if only is None or only:
            n = link_feed_items(db, qdrant, collection, lookup=lookup, only_ids=only, dry_run=dry_run)
            print(f"feed items: updated={n}")

    if not dry_run:
        linked = linked_procedure_ids(qdrant, collection) | _feed_procedure_ids(db)
        flags = {
            vid: vid in linked for vid, record in procedures.items() if record.has_links != (vid in linked)
        }
        store.set_has_links(flags)
        for vid, value in flags.items():
            procedures[vid] = procedures[vid].model_copy(update={"has_links": value})

    print(render(collect(scroll_linkable(qdrant, collection, wahlperioden), procedures)))
    return 1 if failed else 0


def _feed_procedure_ids(db: Any) -> set[str]:
    return {
        vid
        for snapshot in db.collection("feed_items").where("parliament", "==", "bundestag").stream()
        for vid in (snapshot.to_dict() or {}).get("procedure_ids") or []
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--wahlperiode", type=int, nargs="+", default=WAHLPERIODEN)
    parser.add_argument("--backfill", action="store_true", help="sync every in-scope Vorgang")
    parser.add_argument("--link-only", action="store_true", help="skip the DIP sync")
    parser.add_argument("--no-link", action="store_true", help="skip linking votes and speeches")
    parser.add_argument("--no-feed", action="store_true", help="leave feed items as they are")
    parser.add_argument("--report", action="store_true", help="print the coverage report only")
    parser.add_argument("--dry-run", action="store_true", help="read only; write nothing")
    parser.add_argument("--allow-remote", action="store_true", help="write a deployed dev Firestore")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

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
        print(render(collect(scroll_linkable(qdrant, COLLECTION_NAME, args.wahlperiode),
                             ProcedureStore(db).all())))
        return 0
    from wahlchat_common.embeddings import get_embeddings  # noqa: PLC0415

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
        today=date.today(),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.exit(exit_code)
