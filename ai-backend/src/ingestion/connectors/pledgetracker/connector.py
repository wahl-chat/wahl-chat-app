# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PledgeTracker mapper: queue-API results / fixture → PledgeRecord → ChunkRecord.

The official entrypoint is ``python -m src.ingestion.connectors.pledgetracker.bulk``.
That runner owns the queue client (submit/poll) and the registry of pledge
inputs; this module is the pure data transform. Stub mode (the default unless
``PLEDGETRACKER_ENABLE_LIVE`` is truthy) serves the packaged fixture so demo
runs and tests never touch the network.

The connector is deliberately NOT registered in ``registry.CONNECTOR_FACTORIES``:
pledges have no monotonic integer cursor (the generic run.py contract) and the
runner dual-writes Firestore + Qdrant, so a bespoke bulk runner is the fit —
same precedent as manifesto_uploads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import date as date_type
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.pledgetracker.registry import PledgeInput
from src.ingestion.ids import compute_source_item_id, make_chunk_key
from src.ingestion.schemas import AuthorityTier, ChunkRecord, PledgeStatus, SourceType
from src.models.pledge_tracker import PledgeRecord, PledgeTimelineEvent

logger = logging.getLogger(__name__)

_STUB_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "pledge_timeline_spd.json"

_TRUE_VALUES = {"ja", "yes", "true", "1"}
_FALSE_VALUES = {"nein", "no", "false", "0"}


class PledgeTrackerConnector(BaseConnector):
    """Map PledgeTracker payloads to wahl.chat records.

    ``stub`` defaults to True unless ``PLEDGETRACKER_ENABLE_LIVE`` is set to a
    truthy value. In live mode the bulk runner drives the queue client directly
    and uses ``merge_result``; the BaseConnector ``discover``/``fetch`` surface
    only serves the stub/demo path and unit tests.
    """

    source_type: str = SourceType.PLEDGE_RECORD.value

    def __init__(self, stub: Optional[bool] = None) -> None:
        live_enabled = os.getenv("PLEDGETRACKER_ENABLE_LIVE", "").lower() in {
            "1",
            "true",
            "yes",
        }
        self._stub = (not live_enabled) if stub is None else stub
        self._stub_fixture_cache: Optional[dict] = None

    @property
    def is_stub(self) -> bool:
        return self._stub

    # ------------------------------------------------------------------
    # Stub/demo surface (BaseConnector contract; live runs bypass this)
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return pledge IDs to fetch — the fixture pledge in stub mode only."""
        if self._stub:
            fixture = self._load_stub_fixture()
            record = self.normalize_record(fixture)
            return [record.pledge_id]
        raise NotImplementedError(
            "Live PledgeTracker runs are registry-driven — use "
            "src.ingestion.connectors.pledgetracker.bulk with a pledge registry JSONL."
        )

    def fetch(self, external_id: str) -> dict:
        """Fetch a raw payload — the fixture in stub mode only.

        The live queue API has no per-pledge GET: jobs are submitted with full
        pledge inputs and polled. The bulk runner owns that flow via
        PledgeQueueClient.
        """
        if self._stub:
            return self._load_stub_fixture()
        raise NotImplementedError(
            "The queue API is job-based; there is no live fetch(pledge_id). "
            "Use PledgeQueueClient.submit_job/wait_for_job via the bulk runner."
        )

    def _load_stub_fixture(self) -> dict:
        if self._stub_fixture_cache is not None:
            return self._stub_fixture_cache
        if not _STUB_FIXTURE_PATH.exists():
            raise FileNotFoundError(f"Stub fixture not found at {_STUB_FIXTURE_PATH}")
        with _STUB_FIXTURE_PATH.open("r", encoding="utf-8") as f:
            self._stub_fixture_cache = json.load(f)
        return self._stub_fixture_cache

    # ------------------------------------------------------------------
    # Live mapping: registry input + queue result → PledgeRecord
    # ------------------------------------------------------------------

    def merge_result(self, pledge: PledgeInput, result: dict) -> PledgeRecord:
        """Merge a registry pledge with its queue-API result into the record.

        The API result carries only the pipeline output (events, status,
        language); everything descriptive (claim, party, region, source
        provenance) comes from our registry row.

        Raises:
            ValueError: when the result has no usable ``events`` list — the
                runner records this as a failure and moves on. An EMPTY list is
                valid (no evidence found yet) and still produces a record, so
                the freshness watermark prevents daily GPU re-runs.
        """
        raw_events = result.get("events")
        if not isinstance(raw_events, list):
            raise ValueError(
                f"Queue result for pledge {pledge.resolved_pledge_id()!r} has no "
                f"events list (result status: {result.get('status')!r})."
            )

        return PledgeRecord(
            pledge_id=pledge.resolved_pledge_id(),
            party_id=pledge.resolved_party_id(),
            claim=pledge.claim,
            normalized_summary=pledge.normalized_summary or pledge.claim,
            region_path=pledge.region_path,
            region=pledge.region,
            context_id=pledge.context_id,
            policy_area=pledge.policy_area,
            pledge_date=pledge.pledge_date,
            pledge_source_title=pledge.pledge_source_title,
            pledge_source_url=pledge.pledge_source_url,
            pledge_source_locator=pledge.pledge_source_locator,
            timeline_events=[_normalize_event(event) for event in raw_events],
            last_checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            tracker_status=PledgeStatus.IN_PROGRESS.value,
        )

    # ------------------------------------------------------------------
    # Fixture-shaped mapping (stub/demo + tests)
    # ------------------------------------------------------------------

    def normalize_record(self, raw: dict) -> PledgeRecord:
        """Map a fixture-shaped payload to the Firestore source-of-truth schema."""
        party_id = raw.get("party_id") or raw.get("party") or "unknown"
        claim = raw.get("claim") or raw.get("claim_text") or raw.get("label")
        claim = claim or raw.get("claim_id") or "Unbekanntes Versprechen"
        normalized_summary = raw.get("normalized_summary") or raw.get("summary") or claim

        region_path = raw.get("region_path") or ["DE"]
        region = raw.get("region") or region_path[-1]

        pledge_id = raw.get("pledge_id") or str(
            compute_source_item_id(
                SourceType.PLEDGE_RECORD.value,
                f"{party_id}:{claim}:{region}",
            )
        )

        events = [_normalize_event(event) for event in raw.get("events", [])]
        last_checked_at = raw.get("last_checked_at") or raw.get("timestamp")
        if last_checked_at is None:
            last_checked_at = date_type.today().isoformat()

        return PledgeRecord(
            pledge_id=pledge_id,
            party_id=party_id,
            claim=claim,
            normalized_summary=normalized_summary,
            region_path=region_path,
            region=region,
            context_id=raw.get("context_id"),
            policy_area=raw.get("policy_area"),
            pledge_date=raw.get("pledge_date"),
            pledge_source_title=raw.get("pledge_source_title"),
            pledge_source_url=raw.get("pledge_source_url"),
            pledge_source_locator=raw.get("pledge_source_locator"),
            timeline_events=events,
            last_checked_at=last_checked_at,
            tracker_status=raw.get("tracker_status") or PledgeStatus.IN_PROGRESS.value,
            tracker_status_label=raw.get("tracker_status_label"),
            tracker_step=raw.get("tracker_step"),
        )

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Map a fixture-shaped payload to one lightweight Qdrant chunk."""
        return [self.to_chunk(self.normalize_record(raw))]

    def to_chunk(self, record: PledgeRecord) -> ChunkRecord:
        """Build the searchable pledge vector payload.

        One vector per pledge, no chunking (same pattern as vote records).
        Timeline events intentionally stay out of the embedded text; Firestore
        is the source of truth for the full timeline.
        """
        source_item_id = compute_source_item_id(
            SourceType.PLEDGE_RECORD.value,
            record.pledge_id,
        )
        publish_date = _parse_date(record.pledge_date) or date_type.today()
        policy_area = record.policy_area or "unbekannt"
        text = (
            f"Versprechen: {record.claim}\n"
            f"Zusammenfassung: {record.normalized_summary}\n"
            f"Partei: {record.party_id}\n"
            f"Politikfeld: {policy_area}\n"
            f"Region: {' > '.join(record.region_path)}"
        )
        # Change-aware idempotency: a refreshed pledge (new status/check date)
        # re-writes the same point instead of being skipped as unchanged.
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": text,
                    "status": record.tracker_status,
                    "as_of": record.last_checked_at,
                    "context_id": record.context_id,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        return ChunkRecord(
            chunk_key=make_chunk_key(source_item_id, 0),
            source_item_id=source_item_id,
            chunk_index=0,
            text=text,
            party_id=record.party_id,
            region=record.region,
            authority_tier=AuthorityTier.SELF_REPORTED,
            source_type=SourceType.PLEDGE_RECORD,
            publish_date=publish_date,
            citation_title=f"Versprechen: {record.claim}",
            citation_url=record.pledge_source_url,
            external_id=None,
            source_parent_key=f"{SourceType.PLEDGE_RECORD.value}:{record.pledge_id}",
            content_hash=content_hash,
            status=record.tracker_status,
            as_of_date=_parse_date(record.last_checked_at) or date_type.today(),
            claim_id=record.pledge_id,
            pledge_id=record.pledge_id,
            policy_area=record.policy_area,
            context_id=record.context_id,
        )


def _normalize_event(raw: dict) -> PledgeTimelineEvent:
    """Map one queue-API/fixture event to the timeline schema.

    ``content`` (the full source text) is intentionally NOT stored: Firestore
    docs cap at 1MB and the ``url``/``title`` already identify the source.
    """
    raw_label = raw.get("label")
    label_bool = _label_to_bool(raw_label)
    confidence = raw.get("confident")
    if confidence is None:
        confidence = raw.get("confidence")

    return PledgeTimelineEvent(
        date=str(raw.get("date") or ""),
        publication_date=raw.get("publication_date")
        or raw.get("event date (publication date if different)"),
        event=raw.get("event") or raw.get("description") or "",
        event_short=raw.get("event_short"),
        url=raw.get("url"),
        title=raw.get("title"),
        bundesland=raw.get("bundesland"),
        source=raw.get("quelle") or raw.get("source"),
        party=raw.get("partei") or raw.get("party"),
        actor_type=raw.get("urheber_typ") or raw.get("actor_type"),
        is_relevant_for_tracking=label_bool,
        raw_label=raw_label,
        confidence=confidence,
    )


def _label_to_bool(label: object) -> Optional[bool]:
    if label is None:
        return None
    normalized = str(label).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def _parse_date(value: Optional[str]) -> Optional[date_type]:
    if not value:
        return None
    try:
        return date_type.fromisoformat(value[:10])
    except ValueError:
        return None
