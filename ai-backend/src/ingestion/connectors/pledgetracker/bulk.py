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
    for the 15-minute scheduled-job cap, like the other incremental runners).

Usage (local):
    FIRESTORE_EMULATOR_HOST=localhost:8081 PLEDGETRACKER_ENABLE_LIVE=true \
        uv run python -m src.ingestion.connectors.pledgetracker.bulk --batch-size 2
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, Optional

from qdrant_client import QdrantClient

from src.ingestion.connectors.pledgetracker.client import PledgeQueueClient
from src.ingestion.connectors.pledgetracker.connector import PledgeTrackerConnector
from src.ingestion.connectors.pledgetracker.registry import (
    PledgeInput,
    load_pledge_registry,
)
from src.ingestion.connectors.pledgetracker.titles import add_short_titles
from src.ingestion.run import RunReport, _embed_texts, _upsert_chunks
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


def _guard_firestore_target() -> None:
    """Prevent accidental dev/local writes to real Firestore."""
    env = os.getenv("ENV", "dev")
    if env != "prod" and not os.getenv("FIRESTORE_EMULATOR_HOST"):
        raise RuntimeError(
            "FIRESTORE_EMULATOR_HOST is required for PledgeTracker ingestion "
            "when ENV is not prod. Set it to localhost:8081 for local runs."
        )


def _write_pledge_record(db, record: PledgeRecord) -> None:  # type: ignore[no-untyped-def]
    db.collection("pledges").document(record.pledge_id).set(
        record.model_dump(mode="json"),
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

            _write_pledge_record(db, record)
            vectors = _embed_texts(embed, [chunk.text])
            _upsert_chunks(qdrant, collection_name, [chunk], vectors)
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
    # Select the batch: first N pledges that are missing or stale.
    # ------------------------------------------------------------------
    actionable: list[tuple[PledgeInput, dict]] = []
    skipped_fresh = 0
    stale_beyond_batch = 0

    for pledge in pledge_inputs:
        pledge_id = pledge.resolved_pledge_id()
        snapshot = db.collection("pledges").document(pledge_id).get()
        doc_data = (snapshot.to_dict() or {}) if snapshot.exists else {}

        if not force and _is_fresh(doc_data, freshness_days):
            skipped_fresh += 1
            continue
        if len(actionable) < batch_size:
            actionable.append((pledge, doc_data))
        else:
            stale_beyond_batch += 1

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
                "pledgetracker_job_submitted_at": datetime.now(
                    timezone.utc
                ).isoformat(timespec="seconds"),
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
            doc_ref.set({"pledgetracker_last_error": submit_error}, merge=True)
            failed += 1
            continue

        try:
            result = client.wait_for_job(job_id)
            record = connector.merge_result(pledge, result)
            # Best-effort compact headlines for the UI; failures leave
            # event_short=None and the frontend falls back to full text.
            add_short_titles(record)

            _write_pledge_record(db, record)
            doc_ref.set({"pledgetracker_last_error": None}, merge=True)

            chunk = connector.to_chunk(record)
            vectors = _embed_texts(embed, [chunk.text])
            _upsert_chunks(qdrant, collection_name, [chunk], vectors)
        except Exception as exc:  # noqa: BLE001
            print(
                f"WARNING: pledge {pledge_id} (job {job_id}) failed: {exc}",
                file=sys.stderr,
            )
            doc_ref.set({"pledgetracker_last_error": str(exc)}, merge=True)
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
        "--backfill-titles",
        action="store_true",
        help=(
            "Only add missing event_short headlines to pledges already in "
            "Firestore (LLM calls, but no queue jobs / GPU / Qdrant writes)"
        ),
    )
    args = parser.parse_args()

    try:
        _guard_firestore_target()

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
    except Exception:  # noqa: BLE001
        import traceback

        print("ERROR: PledgeTracker ingestion failed:", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
