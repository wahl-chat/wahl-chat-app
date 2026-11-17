# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Keep procedures in step with DIP: a full backfill or the changes since the
last successful run (DIP ``aktualisiert``)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from qdrant_client import QdrantClient

from ingestion.procedures.dip import DipReader
from ingestion.procedures.mapper import build_record, profile_chunk
from ingestion.procedures.scope import CORE_TYPES, EXCLUDED_TYPES, in_scope
from ingestion.procedures.store import ProcedureStore, replace_parents
from wahlchat_common.procedures import ProcedureRecord

logger = logging.getLogger(__name__)

_BATCH = 100
# DIP's aktualisiert has minute precision and edits land out of order; the
# overlap re-reads a day, and unchanged procedures cost no writes.
_WATERMARK_OVERLAP = timedelta(days=1)


@dataclass
class SyncReport:
    seen: int = 0
    in_scope: int = 0
    written: int = 0
    unchanged: int = 0
    new_stage: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    changed_sachgebiete: list[str] = field(default_factory=list)


def _has_bt_plenary_stage(positions: list[dict[str, Any]]) -> bool:
    return any(
        p.get("zuordnung") == "BT"
        and (p.get("fundstelle") or {}).get("dokumentart") == "Plenarprotokoll"
        for p in positions
    )


def _batches(ids: Iterable[str], size: int) -> Iterator[list[str]]:
    ordered = sorted(set(ids), key=lambda v: (len(v), v))
    for start in range(0, len(ordered), size):
        yield ordered[start : start + size]


def backfill_ids(dip: DipReader, wahlperioden: Iterable[int]) -> set[str]:
    """Every in-scope Vorgang id: core types plus anything with a BT plenary stage."""
    ids: set[str] = set()
    for wp in wahlperioden:
        plenary = dip.plenary_vorgang_types(wp)
        ids.update(vid for vid, typ in plenary.items() if typ not in EXCLUDED_TYPES)
        ids.update(dip.vorgang_ids_of_types(wp, CORE_TYPES))
    return ids


def sync_ids(
    ids: Iterable[str],
    *,
    dip: DipReader,
    store: ProcedureStore,
    qdrant: QdrantClient,
    collection: str,
    embed: Any,
    today: date,
    dry_run: bool = False,
    verify_chunks: bool = False,
) -> SyncReport:
    """Fetch, map and write the given Vorgänge; out-of-scope ones are skipped.

    ``verify_chunks`` also hands unchanged records' profile chunks to the
    writer, which re-creates any that are missing from Qdrant (a rebuilt
    collection) and skips the rest by their hashes.

    Per batch the profile chunks are written first and the Firestore records
    after, so a stored record means its chunk is there too. A batch that
    fails is reported by id and retried by the next run.
    """
    report = SyncReport()
    for batch in _batches(ids, _BATCH):
        try:
            vorgaenge = dip.vorgaenge(batch)
            positions = dip.positions(list(vorgaenge))
            previous = store.get(vorgaenge)
        except Exception:  # noqa: BLE001 — retried next run
            logger.exception("DIP or Firestore read failed for %d Vorgänge", len(batch))
            report.failed.extend(batch)
            continue
        report.seen += len(vorgaenge)

        changed: list[ProcedureRecord] = []
        unchanged: list[ProcedureRecord] = []
        for vid, vorgang in vorgaenge.items():
            mine = positions.get(vid, [])
            if not in_scope(
                vorgang.get("vorgangstyp") or "", _has_bt_plenary_stage(mine)
            ):
                continue
            report.in_scope += 1
            old = previous.get(vid)
            try:
                record = build_record(vorgang, mine, previous=old, today=today)
            except Exception:  # noqa: BLE001 — one malformed Vorgang must not stop the run
                logger.exception("Vorgang %s could not be mapped", vid)
                report.failed.append(vid)
                continue
            if old is not None and old.content_hash == record.content_hash:
                report.unchanged += 1
                unchanged.append(record)
                continue
            changed.append(record)
            if old is None:
                report.created.append(vid)
            if (
                old is not None
                and record.stage_changed_on == today != old.stage_changed_on
            ):
                report.new_stage.append(vid)
            if old is not None and old.sachgebiete != record.sachgebiete:
                report.changed_sachgebiete.append(vid)
        if dry_run:
            report.written += len(changed)  # would write
            continue
        to_check = changed + (unchanged if verify_chunks else [])
        if not to_check:
            continue

        parents = {
            f"procedure:{r.vorgang_id}": [profile_chunk(r, today=today)]
            for r in to_check
        }
        written = replace_parents(qdrant, collection, embed, parents)
        failed = {key.split(":", 1)[1] for key in written.failed_parents}
        ok = [r for r in changed if r.vorgang_id not in failed]
        try:
            store.put(ok)
        except Exception:  # noqa: BLE001 — retried next run
            logger.exception("Firestore write failed for %d procedures", len(ok))
            failed.update(r.vorgang_id for r in ok)
            ok = []
        report.written += len(ok)
        report.failed.extend(sorted(failed))
    return report


def run_sync(
    *,
    dip: DipReader,
    store: ProcedureStore,
    qdrant: QdrantClient,
    collection: str,
    embed: Any,
    wahlperioden: list[int],
    backfill: bool,
    today: date,
    now: Optional[datetime] = None,
    dry_run: bool = False,
) -> SyncReport:
    """Backfill or delta, then persist the watermark.

    The watermark moves to this run's start when the run had no failure (or
    was a backfill, which listed everything); failed ids are kept and tried
    first next time either way.
    """
    started = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    state = store.sync_state()
    retry = set(state.get("failed_ids") or [])
    if backfill:
        ids = backfill_ids(dip, wahlperioden)
    else:
        mark = state.get("dip_updated_through")
        if not mark:
            raise RuntimeError(
                "No sync watermark yet: run the backfill first (--backfill)."
            )
        since = (datetime.fromisoformat(mark) - _WATERMARK_OVERLAP).isoformat()
        ids = set()
        for wp in wahlperioden:
            ids.update(dip.updated_vorgang_ids(wp, since))
    ids |= retry
    logger.info("Syncing %d Vorgänge (%d retried)", len(ids), len(retry))

    report = sync_ids(
        ids,
        dip=dip,
        store=store,
        qdrant=qdrant,
        collection=collection,
        embed=embed,
        today=today,
        dry_run=dry_run,
        verify_chunks=backfill,
    )
    if not dry_run:
        new_state: dict[str, Any] = {"failed_ids": sorted(set(report.failed))}
        if report.failed and not backfill:
            new_state["dip_updated_through"] = state.get("dip_updated_through")
        else:
            new_state["dip_updated_through"] = started.isoformat()
        new_state["last_run_at"] = started.isoformat()
        store.set_sync_state({**state, **new_state})
    return report
