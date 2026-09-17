# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firestore + Qdrant ingestion runner for PledgeTracker records.

Two modes, selected by ``PLEDGETRACKER_ENABLE_LIVE``:

Stub (default): ingest the packaged fixture — the offline demo path.

Live: registry-driven. Each pledge in the registry JSONL is submitted as a job
to the Cambridge queue API (one GPU, one job at a time, ~3 min each), polled
until done, then written to Firestore (full record) and Qdrant (one lightweight
chunk). Because runs are slow and serialized, the runner is incremental:

  - freshness watermark: pledges checked within ``--freshness-days`` are
    skipped (override with ``--force``);
  - crash-safe resume: the job id is merge-written to the Firestore doc at
    submit time, so a rerun re-fetches the stored server-side result instead
    of burning another GPU run;
  - bounded batches: at most ``--batch-size`` pledges per invocation (shaped
    for the 15-minute scheduled-job cap, like the other incremental runners);
  - bounded retries: failures stamp ``pledgetracker_last_attempted_at`` and the
    batch takes the least-recently-touched pledges first, so a permanently
    failing pledge cannot occupy a batch slot on every run;
  - reconcile: after a live run, pledges present in the stores but absent from
    the registry (edited claims, removed rows) are retired, scoped to the
    registry's own regions (``--skip-reconcile`` opts out).

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 PLEDGETRACKER_ENABLE_LIVE=true \
        uv run python -m src.ingestion.connectors.pledgetracker.bulk --batch-size 2
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, Optional

from qdrant_client import QdrantClient, models

from src.ingestion.connectors.pledgetracker.client import PledgeQueueClient
from src.ingestion.connectors.pledgetracker.connector import PledgeTrackerConnector
from src.ingestion.connectors.pledgetracker.registry import (
    PledgeInput,
    load_pledge_registry,
)
from src.ingestion.connectors.pledgetracker.titles import add_short_titles
from src.ingestion.run import RunReport, _embed_texts, _upsert_chunks
from src.ingestion.schemas import SourceType
from src.ingestion.setup_collection import COLLECTION_NAME, check_fingerprint
from src.models.pledge_tracker import PledgeRecord

logger = logging.getLogger(__name__)

_DEFAULT_REGISTRY = "data/pledges/sample_pledges.jsonl"


class LiveRunReport(NamedTuple):
    processed: int
    skipped_fresh: int
    failed: int
    remaining: int
    chunks_upserted: int


def _guard_firestore_target(allow_remote: bool = False) -> None:
    """Prevent ACCIDENTAL non-emulator writes outside prod.

    ENV=prod targets real Firestore as before. Every other ENV requires the
    emulator unless ``--allow-remote`` is passed explicitly — the deliberate
    path for ingesting pledges into the deployed ENV Firebase project
    (typically the hosted dev environment).

    ``--allow-remote`` unsets ``FIRESTORE_EMULATOR_HOST``: local ``.env`` and
    the Makefile routinely set it for emulator-mode development, and
    ``firebase_service`` keys off that variable at import time. Leaving it in
    place would make the flag a no-op and keep writing to the emulator.
    """
    if allow_remote:
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
    env = os.getenv("ENV", "dev")
    if env == "prod" or os.getenv("FIRESTORE_EMULATOR_HOST"):
        return
    if allow_remote:
        logger.warning(
            "PledgeTracker ingestion writing to REMOTE Firestore with ENV=%s "
            "(--allow-remote).",
            env,
        )
        return
    raise RuntimeError(
        "FIRESTORE_EMULATOR_HOST is required for PledgeTracker ingestion when "
        "ENV is not prod. Set it to localhost:8081 for local runs, or pass "
        "--allow-remote to ingest into a deployed dev environment on purpose."
    )


def _write_pledge_record(db, record: PledgeRecord) -> None:  # type: ignore[no-untyped-def]
    # exclude_none with merge=True: a registry row that omits optional metadata
    # (context_id, source title/url) must not overwrite a richer stored record
    # with explicit nulls.
    db.collection("pledges").document(record.pledge_id).set(
        record.model_dump(mode="json", exclude_none=True),
        merge=True,
    )


def _parse_checked_at(value: object) -> Optional[datetime]:
    """Parse last_checked_at defensively; unparseable → None (treated as stale)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(value[:10])
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_fresh(doc_data: dict, freshness_days: int) -> bool:
    checked_at = _parse_checked_at(doc_data.get("last_checked_at"))
    if checked_at is None:
        return False
    return datetime.now(timezone.utc) - checked_at < timedelta(days=freshness_days)


_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _last_activity(doc_data: dict) -> datetime:
    """Most recent successful check OR failed attempt; never-touched → epoch.

    Batch-ordering key: oldest activity first, so pledges that keep failing
    rotate to the back of the queue instead of starving the rest of the
    registry, and brand-new pledges go first.
    """
    stamps = [
        _parse_checked_at(doc_data.get("last_checked_at")),
        _parse_checked_at(doc_data.get("pledgetracker_last_attempted_at")),
    ]
    known = [stamp for stamp in stamps if stamp is not None]
    return max(known) if known else _EPOCH


def _resumable_job_id(doc_data: dict) -> Optional[int]:
    """Job id from a previous run that never finished writing its result.

    A submit merge-writes {job_id, submitted_at}; a completed run then writes
    last_checked_at >= submitted_at. So a job id with submitted_at NEWER than
    last_checked_at (or no last_checked_at at all) marks an interrupted run
    whose server-side result can be re-fetched for free.
    """
    job_id = doc_data.get("pledgetracker_job_id")
    if not isinstance(job_id, int):
        return None
    submitted_at = _parse_checked_at(doc_data.get("pledgetracker_job_submitted_at"))
    checked_at = _parse_checked_at(doc_data.get("last_checked_at"))
    if submitted_at is None:
        return None
    if checked_at is None or submitted_at > checked_at:
        return job_id
    return None


# ---------------------------------------------------------------------------
# Stub mode — packaged fixture, no network (offline demo)
# ---------------------------------------------------------------------------


def run_pledgetracker_stub(
    connector: PledgeTrackerConnector,
    qdrant: QdrantClient,
    embed,  # type: ignore[no-untyped-def]
    db,  # type: ignore[no-untyped-def]
    collection_name: str = COLLECTION_NAME,
    *,
    batch_size: int = 50,
) -> RunReport:
    """Stub ingestion: fixture pledges into Firestore and Qdrant."""
    pledge_ids = connector.discover(since=None)
    batch = pledge_ids[:batch_size]

    processed = 0
    chunks_upserted = 0

    for pledge_id in batch:
        try:
            raw = connector.fetch(pledge_id)
            record = connector.normalize_record(raw)
            chunk = connector.to_chunk(record)

            # Qdrant BEFORE Firestore: the Firestore write carries
            # last_checked_at, i.e. the freshness watermark. Dying between the
            # writes in this order leaves a vector without a fresh doc — the
            # next run simply redoes the pledge. The reverse order would mark
            # it fresh WITHOUT a vector, hiding it from retrieval for a full
            # freshness window. (A vector whose doc is missing is tolerated at
            # read time: hydration skips it as a stale point.)
            vectors = _embed_texts(embed, [chunk.text])
            _upsert_chunks(qdrant, collection_name, [chunk], vectors)
            _write_pledge_record(db, record)
        except Exception as exc:  # noqa: BLE001
            print(f"WARNING: skipping pledge {pledge_id}: {exc}", file=sys.stderr)
            continue

        processed += 1
        chunks_upserted += 1

    return RunReport(
        processed=processed,
        remaining=max(0, len(pledge_ids) - processed),
        chunks_upserted=chunks_upserted,
    )


# ---------------------------------------------------------------------------
# Live mode — Cambridge queue API, registry-driven, incremental
# ---------------------------------------------------------------------------


def run_pledgetracker_live(
    client: PledgeQueueClient,
    connector: PledgeTrackerConnector,
    qdrant: QdrantClient,
    embed,  # type: ignore[no-untyped-def]
    db,  # type: ignore[no-untyped-def]
    registry_path: str | Path,
    collection_name: str = COLLECTION_NAME,
    *,
    batch_size: int = 3,
    freshness_days: int = 7,
    force: bool = False,
) -> LiveRunReport:
    """Submit stale registry pledges as queue jobs and ingest their results."""
    pledge_inputs = load_pledge_registry(registry_path)

    # ------------------------------------------------------------------
    # Select the batch: stale pledges, least-recently-touched first. Registry
    # order alone would let a few permanently failing rows at the top occupy
    # every batch; ordering by last activity (check or attempt) rotates them
    # to the back and lets the rest of the registry through.
    # ------------------------------------------------------------------
    stale: list[tuple[PledgeInput, dict]] = []
    skipped_fresh = 0

    for pledge in pledge_inputs:
        pledge_id = pledge.resolved_pledge_id()
        snapshot = db.collection("pledges").document(pledge_id).get()
        doc_data = (snapshot.to_dict() or {}) if snapshot.exists else {}

        if not force and _is_fresh(doc_data, freshness_days):
            skipped_fresh += 1
            continue
        stale.append((pledge, doc_data))

    stale.sort(key=lambda item: _last_activity(item[1]))
    actionable = stale[:batch_size]
    stale_beyond_batch = len(stale) - len(actionable)

    # ------------------------------------------------------------------
    # Phase A: resolve a job id per pledge — resume an interrupted job when
    # possible (the server stores finished results), otherwise submit a new
    # one. Jobs are submitted upfront; the server queues them (one GPU, FIFO).
    # ------------------------------------------------------------------
    jobs: list[tuple[PledgeInput, Optional[int], Optional[str]]] = []
    for pledge, doc_data in actionable:
        pledge_id = pledge.resolved_pledge_id()
        resumable = _resumable_job_id(doc_data)
        if resumable is not None:
            try:
                status = client.get_job(resumable).get("status")
                if status in {"queued", "running", "done"}:
                    print(f"pledge {pledge_id}: resuming job {resumable} ({status})")
                    jobs.append((pledge, resumable, None))
                    continue
            except Exception as exc:  # noqa: BLE001
                print(
                    f"pledge {pledge_id}: stored job {resumable} not reusable "
                    f"({exc}) — submitting a new one",
                    file=sys.stderr,
                )
        try:
            new_job_id = client.submit_job(pledge.job_inputs())
        except Exception as exc:  # noqa: BLE001
            jobs.append((pledge, None, f"submit failed: {exc}"))
            continue
        # Crash-safe resume point: persist the job id before polling.
        db.collection("pledges").document(pledge_id).set(
            {
                "pledgetracker_job_id": new_job_id,
                "pledgetracker_job_submitted_at": datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                ),
            },
            merge=True,
        )
        jobs.append((pledge, new_job_id, None))

    # ------------------------------------------------------------------
    # Phase B: poll each job in submission order; write stores on success.
    # ------------------------------------------------------------------
    processed = 0
    failed = 0
    chunks_upserted = 0

    for pledge, job_id, submit_error in jobs:
        pledge_id = pledge.resolved_pledge_id()
        doc_ref = db.collection("pledges").document(pledge_id)

        if job_id is None:
            print(f"WARNING: pledge {pledge_id}: {submit_error}", file=sys.stderr)
            doc_ref.set(
                {
                    "pledgetracker_last_error": submit_error,
                    "pledgetracker_last_attempted_at": _now_iso(),
                },
                merge=True,
            )
            failed += 1
            continue

        try:
            result = client.wait_for_job(job_id)
            record = connector.merge_result(pledge, result)
            # Best-effort compact headlines for the UI; failures leave
            # event_short=None and the frontend falls back to full text.
            add_short_titles(record)

            # Qdrant BEFORE Firestore: _write_pledge_record persists
            # last_checked_at (the freshness watermark). Dying between the
            # writes in this order leaves a vector without a fresh doc, and the
            # resume path redoes the pledge next run. The reverse order marked
            # the pledge fresh WITHOUT a vector — invisible to retrieval for a
            # full freshness window, unrecoverable by resume. (A vector whose
            # doc is stale is tolerated at read time by aget_pledges_by_ids.)
            chunk = connector.to_chunk(record)
            vectors = _embed_texts(embed, [chunk.text])
            _upsert_chunks(qdrant, collection_name, [chunk], vectors)

            _write_pledge_record(db, record)
            doc_ref.set({"pledgetracker_last_error": None}, merge=True)
        except Exception as exc:  # noqa: BLE001
            print(
                f"WARNING: pledge {pledge_id} (job {job_id}) failed: {exc}",
                file=sys.stderr,
            )
            # The attempt stamp feeds _last_activity, so this pledge yields its
            # batch slot to the rest of the registry until everything else had
            # a turn. The job id is kept: a transient failure (embedding
            # outage) can still resume the stored server-side result for free.
            doc_ref.set(
                {
                    "pledgetracker_last_error": str(exc),
                    "pledgetracker_last_attempted_at": _now_iso(),
                },
                merge=True,
            )
            failed += 1
            continue

        processed += 1
        chunks_upserted += 1
        print(
            f"pledge {pledge_id}: ingested {len(record.timeline_events)} events "
            f"(job {job_id})"
        )

    return LiveRunReport(
        processed=processed,
        skipped_fresh=skipped_fresh,
        failed=failed,
        remaining=stale_beyond_batch,
        chunks_upserted=chunks_upserted,
    )


def _stale_pledge_ids(registry_ids: set[str], existing_ids: Iterable[str]) -> set[str]:
    """Pledge ids present in the stores but absent from the registry."""
    return {pledge_id for pledge_id in existing_ids if pledge_id not in registry_ids}


class ReconcileBlocked(RuntimeError):
    """Reconcile would retire more pledges than the registry manages."""


def reconcile_registry(
    qdrant: QdrantClient,
    db,  # type: ignore[no-untyped-def]
    pledge_inputs: list[PledgeInput],
    collection_name: str = COLLECTION_NAME,
    *,
    force: bool = False,
) -> tuple[int, int]:
    """Retire pledges that are no longer in the registry (edited or removed).

    The pledge id contains the claim text, so editing a claim mints a NEW id —
    without this step the old Firestore doc and Qdrant point stay publicly
    readable and retrievable forever (same for deleted rows). Scoped to the
    registry's own regions — the pledge-side equivalent of the manifesto
    supersede rule.

    Region scope alone is not a sufficient guard: two registries covering the
    same region would each see the other's pledges as stale. So a run that
    would retire more pledges than the registry itself manages is refused —
    the signature of the wrong registry file or a truncated one. ``force``
    overrides it for a deliberate bulk retirement.

    Returns:
        (qdrant_points_deleted, firestore_docs_deleted)

    Raises:
        ReconcileBlocked: the retire set is implausibly large and force is off.
    """
    registry_ids = {pledge.resolved_pledge_id() for pledge in pledge_inputs}
    regions = {pledge.region for pledge in pledge_inputs}
    if not regions:
        return (0, 0)

    # Qdrant: collect pledge_record points inside the registry's regions.
    point_ids_by_pledge: dict[str, list] = {}
    scroll_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="source_type",
                match=models.MatchValue(value=SourceType.PLEDGE_RECORD.value),
            ),
            models.FieldCondition(
                key="region", match=models.MatchAny(any=sorted(regions))
            ),
        ]
    )
    offset = None
    while True:
        points, offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=256,
            offset=offset,
            with_payload=["pledge_id"],
            with_vectors=False,
        )
        for point in points:
            pledge_id = (point.payload or {}).get("pledge_id")
            if isinstance(pledge_id, str):
                point_ids_by_pledge.setdefault(pledge_id, []).append(point.id)
        if offset is None:
            break

    stale_ids = _stale_pledge_ids(registry_ids, point_ids_by_pledge)

    # Firestore can be wider than Qdrant (e.g. a crash left a doc without a
    # vector), so scan the collection too — same region scope. Docs carrying
    # only ops fields have no region yet and are left alone.
    stale_doc_ids = [
        snapshot.id
        for snapshot in db.collection("pledges").stream()
        if (snapshot.to_dict() or {}).get("region") in regions
        and snapshot.id not in registry_ids
    ]

    # Decide before deleting anything.
    retire_count = len(stale_ids | set(stale_doc_ids))
    if not force and retire_count > len(registry_ids):
        raise ReconcileBlocked(
            f"Reconcile would retire {retire_count} pledge(s) in regions "
            f"{sorted(regions)} while the registry manages only "
            f"{len(registry_ids)} — refusing. This usually means the wrong "
            f"--registry file, or a registry that lost rows. Re-run with "
            f"--force-reconcile if the retirement is intended."
        )

    stale_point_ids = [
        point_id
        for pledge_id in stale_ids
        for point_id in point_ids_by_pledge[pledge_id]
    ]
    if stale_point_ids:
        qdrant.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=stale_point_ids),
        )

    for doc_id in stale_doc_ids:
        db.collection("pledges").document(doc_id).delete()
        print(f"reconcile: retired pledge {doc_id}")

    return (len(stale_point_ids), len(stale_doc_ids))


def backfill_titles(db) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Add missing event_short headlines to existing Firestore pledge docs.

    Reads every pledges/* doc, generates headlines only for events without one,
    and merge-writes changed docs back. No queue jobs, no GPU time, no Qdrant
    writes (timelines are never embedded).

    Returns:
        (docs_updated, titles_added)
    """
    docs_updated = 0
    titles_added = 0
    for snapshot in db.collection("pledges").stream():
        data = snapshot.to_dict() or {}
        try:
            record = PledgeRecord(**data)
        except Exception as exc:  # noqa: BLE001
            print(
                f"WARNING: skipping malformed pledge doc {snapshot.id}: {exc}",
                file=sys.stderr,
            )
            continue

        added = add_short_titles(record)
        if added > 0:
            _write_pledge_record(db, record)
            docs_updated += 1
            titles_added += added
            print(f"pledge {record.pledge_id}: added {added} short titles")
        else:
            print(f"pledge {record.pledge_id}: up to date (no titles added)")
    return docs_updated, titles_added


def _dry_run(db, registry_path: str | Path, freshness_days: int, force: bool) -> None:  # type: ignore[no-untyped-def]
    """Print the run plan (fresh/stale per pledge) without touching API or stores."""
    pledge_inputs = load_pledge_registry(registry_path)
    print(f"Registry: {registry_path} — {len(pledge_inputs)} pledges")
    for pledge in pledge_inputs:
        pledge_id = pledge.resolved_pledge_id()
        snapshot = db.collection("pledges").document(pledge_id).get()
        doc_data = (snapshot.to_dict() or {}) if snapshot.exists else {}
        if not force and _is_fresh(doc_data, freshness_days):
            verdict = "SKIP (fresh)"
        elif _resumable_job_id(doc_data) is not None:
            verdict = f"RESUME job {doc_data.get('pledgetracker_job_id')}"
        else:
            verdict = "SUBMIT"
        print(
            f"  {verdict:>14}  {pledge.resolved_party_id():>10}  "
            f"{pledge.region:>5}  {pledge_id}"
        )


if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Run PledgeTracker Firestore + Qdrant ingestion."
    )
    parser.add_argument(
        "--registry",
        default=os.getenv("PLEDGETRACKER_REGISTRY", _DEFAULT_REGISTRY),
        help=f"Pledge registry JSONL path (default: {_DEFAULT_REGISTRY})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Maximum pledges to process this run (default: 3; ~3 min GPU time each)",
    )
    parser.add_argument(
        "--freshness-days",
        type=int,
        default=7,
        help="Skip pledges checked within this many days (default: 7)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the freshness watermark and re-run every registry pledge",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the run plan (submit/resume/skip) without API or store writes",
    )
    parser.add_argument(
        "--skip-reconcile",
        action="store_true",
        help=(
            "Skip retiring pledges that are in the stores but no longer in the "
            "registry (reconcile is scoped to the registry's own regions)"
        ),
    )
    parser.add_argument(
        "--force-reconcile",
        action="store_true",
        help=(
            "Allow reconcile to retire more pledges than the registry manages "
            "(refused by default, since that usually means the wrong registry)"
        ),
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=(
            "Permit writes to non-emulator Firestore when ENV != prod — the "
            "explicit path for ingesting into the deployed dev environment"
        ),
    )
    parser.add_argument(
        "--backfill-titles",
        action="store_true",
        help=(
            "Only add missing event_short headlines to pledges already in "
            "Firestore (LLM calls, but no queue jobs / GPU / Qdrant writes)"
        ),
    )
    args = parser.parse_args()

    try:
        _guard_firestore_target(allow_remote=args.allow_remote)

        # Import after the emulator guard so firebase_admin never initializes
        # against real Firestore by accident during local development.
        from src.firebase_service import db  # noqa: PLC0415

        if args.backfill_titles:
            updated, added = backfill_titles(db)
            print(f"backfill_titles: docs_updated={updated} titles_added={added}")
            sys.exit(0)

        connector = PledgeTrackerConnector()

        if args.dry_run:
            if connector.is_stub:
                print("Stub mode: dry run would ingest the packaged fixture pledge.")
            else:
                _dry_run(db, args.registry, args.freshness_days, args.force)
            sys.exit(0)

        from src.embeddings import get_embeddings  # noqa: PLC0415

        qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )
        check_fingerprint(qdrant, COLLECTION_NAME)
        embed = get_embeddings(task_type="RETRIEVAL_DOCUMENT")

        started = time.monotonic()
        if connector.is_stub:
            report = run_pledgetracker_stub(
                connector, qdrant, embed, db, batch_size=args.batch_size
            )
            if report.processed == 0 and report.remaining > 0:
                raise RuntimeError(
                    "PledgeTracker ingestion processed 0 pledges. "
                    "Check Firestore emulator, Qdrant, and the fixture path."
                )
            duration = time.monotonic() - started
            print(
                f"pledgetracker (stub): processed={report.processed} "
                f"remaining={report.remaining} "
                f"chunks_upserted={report.chunks_upserted} duration={duration:.1f}s"
            )
        else:
            client = PledgeQueueClient()
            if not client.health():
                raise RuntimeError(
                    "PledgeTracker queue API health check failed — is "
                    f"{os.getenv('PLEDGETRACKER_API_URL') or 'the default endpoint'} "
                    "reachable?"
                )
            live_report = run_pledgetracker_live(
                client,
                connector,
                qdrant,
                embed,
                db,
                args.registry,
                batch_size=args.batch_size,
                freshness_days=args.freshness_days,
                force=args.force,
            )
            duration = time.monotonic() - started
            print(
                f"pledgetracker (live): processed={live_report.processed} "
                f"skipped_fresh={live_report.skipped_fresh} "
                f"failed={live_report.failed} remaining={live_report.remaining} "
                f"chunks_upserted={live_report.chunks_upserted} "
                f"duration={duration:.1f}s"
            )
            attempted = live_report.processed + live_report.failed
            if attempted > 0 and live_report.processed == 0:
                raise RuntimeError(
                    "Every attempted PledgeTracker job failed — see warnings above."
                )
            if not args.skip_reconcile:
                points_deleted, docs_deleted = reconcile_registry(
                    qdrant,
                    db,
                    load_pledge_registry(args.registry),
                    force=args.force_reconcile,
                )
                print(
                    f"reconcile: qdrant_points_deleted={points_deleted} "
                    f"firestore_docs_deleted={docs_deleted}"
                )
    except Exception:  # noqa: BLE001
        import traceback

        print("ERROR: PledgeTracker ingestion failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
