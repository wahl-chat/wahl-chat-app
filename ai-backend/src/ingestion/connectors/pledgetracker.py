# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
PledgeTrackerConnector — embed-in-connector for the pledge corpus path.

Pledge fulfillment status is public governmental commitment data, NOT
users/{uid} political-opinion data.  Embedding pledges does NOT breach the GDPR
Art. 9 wall.

This connector is an ORDINARY BaseConnector subclass:
    discover(since) -> list[str]   — re-ingest all each run (no monotonic int cursor)
    fetch(external_id) -> dict     — stub: reads local fixture; live: DEFERRED
    normalize(raw) -> list[ChunkRecord]  — builds one pledge ChunkRecord per item

No Firestore. No GCS. No watermark. Embedding is handled by the runner (run.py).

Security notes:
    SSRF: The live upstream host is pinned as PLEDGETRACKER_HOST (a
    constant, never derived from a method argument or user input).  In STUB mode
    fetch() reads a local fixture file — no network call is made.

    Tampering: extra="forbid" + frozen=True on ChunkRecord rejects
    unknown payload keys.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date as date_type
from pathlib import Path
from typing import Optional

from src.ingestion.connector import BaseConnector
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import (
    AuthorityTier,
    ChunkRecord,
    PledgeStatus,
    SourceType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pinned live upstream host — never user-controlled (SSRF surface = zero).
# LIVE CONFIG IS DEFERRED: the Cambridge /pledge-timeline endpoint is pre-production
# (~mid-June 2026).  The URL below is a placeholder; the exact endpoint path and
# auth scheme must be agreed with the Cambridge team before any live run.
# The claim×party×region config is also team-agreed before live.
PLEDGETRACKER_HOST = "https://pledgetracker.cam.ac.uk"
_LIVE_ENDPOINT_TEMPLATE = PLEDGETRACKER_HOST + "/pledge-timeline"  # TBC with team

# Resolve the fixtures dir from a SINGLE module-level anchor.
# Expected layout (asserted by this comment): this module lives at
#   <ai-backend>/src/ingestion/connectors/pledgetracker.py
# so the ai-backend root is exactly three .parent hops up, and the tests/fixtures
# dir is a sibling of src/.  Keeping the hop-count in one named constant means a
# package-layout refactor only needs to touch this anchor, not scattered paths.
_AI_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_DIR = _AI_BACKEND_ROOT / "tests" / "fixtures"
_STUB_FIXTURE_PATH = _FIXTURES_DIR / "pledge_timeline_spd.json"

# Real PLEDGE_RECORD enum value (replaces VOTE_RECORD workaround).
_SOURCE_TYPE = SourceType.PLEDGE_RECORD


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


class PledgeTrackerConnector(BaseConnector):
    """Embed-in-connector for PledgeTracker pledge timelines.

    Implements the 3-method BaseConnector ABC.  In STUB mode fetch() reads
    a local fixture instead of calling the live /pledge-timeline endpoint (the
    Cambridge endpoint is pre-production — the stub keeps the phase unblocked).

    normalize() returns list[ChunkRecord] with source_type=PLEDGE_RECORD.
    Pledge status/events are public governmental commitment data, NOT
    users/{uid} political-opinion data.  The GDPR Art. 9 wall applies to
    users/ only — embedding pledges does not breach it.

    Args:
        stub: If True (default), fetch() reads the local fixture file instead
              of making an HTTP call to PLEDGETRACKER_HOST.  Set to False only
              when the live Cambridge endpoint is ready and the claim×party×region
              config has been agreed with the team (deferred).
    """

    # Used by runner get_cursor() to scope the Qdrant cursor query.
    source_type: str = SourceType.PLEDGE_RECORD.value

    # Class-level SOURCE_TYPE attribute for external inspection.
    SOURCE_TYPE: str = "pledge_record"

    def __init__(self, stub: bool = True) -> None:
        self._stub = stub
        # Cache the parsed stub fixture so discover() and fetch() do not
        # re-read/re-parse the same JSON file on every call.
        self._stub_fixture_cache: Optional[dict] = None

    # ------------------------------------------------------------------
    # 1. discover
    # ------------------------------------------------------------------

    def discover(self, since: Optional[int]) -> list[str]:
        """Return list of pledge external_ids to process.

        Pledges have no monotonic integer ID — re-ingest all each run.
        The since cursor is intentionally ignored; pledge ChunkRecords are
        idempotent via deterministic compute_chunk_id.

        STUB mode: one triple from fixture.
        LIVE mode: DEFERRED (claim×party×region config).

        Args:
            since: Max external_id cursor from Qdrant — intentionally ignored
                   for pledges (no monotonic int ID).

        Returns:
            List of external ID strings in the format "{party_id}_{claim_id}_{region}".
        """
        if self._stub:
            fixture = self._load_stub_fixture()
            party_id = fixture["party_id"]
            claim_id = fixture["claim_id"]
            region = fixture["region"]
            return [f"{party_id}_{claim_id}_{region}"]
        else:
            # LIVE CONFIG IS DEFERRED — team must agree claim×party×region config
            # before a live run.  Raise explicitly rather than silently returning
            # an empty list to avoid silent no-ops.
            raise NotImplementedError(
                "PledgeTrackerConnector live discover() is DEFERRED: "
                "claim×party×region config must be agreed with the team before a live run. "
                "Set stub=True to use the fixture-based path."
            )

    # ------------------------------------------------------------------
    # 2. fetch
    # ------------------------------------------------------------------

    def fetch(self, external_id: str) -> dict:
        """Fetch the pledge timeline for the given external_id.

        STUB mode: reads the local fixture file (tests/fixtures/pledge_timeline_spd.json)
        instead of calling the live /pledge-timeline endpoint — the Cambridge endpoint
        is pre-production; the stub keeps the phase unblocked.

        LIVE mode (DEFERRED): SSRF mitigation — the live host is the pinned
        constant PLEDGETRACKER_HOST; no user-controlled URL.  The external_id encodes
        party_id/claim_id/region to construct query params (not the host/path).

        Args:
            external_id: "{party_id}_{claim_id}_{region}" triple (from discover()).

        Returns:
            Raw response dict from the endpoint (verbatim).
        """
        if self._stub:
            return self._load_stub_fixture()
        else:
            # SSRF mitigation — host is the pinned constant PLEDGETRACKER_HOST.
            # external_id is used ONLY as a query param value; never used to construct
            # an arbitrary host, path, or redirect.
            import requests  # noqa: PLC0415

            # Parse the external_id back to (party_id, claim_id, region).
            parts = external_id.split("_", 2)
            if len(parts) != 3:
                raise ValueError(f"Invalid external_id format: {external_id!r}")
            party_id, claim_id, region = parts
            resp = requests.get(
                _LIVE_ENDPOINT_TEMPLATE,
                params={"party_id": party_id, "claim_id": claim_id, "region": region},
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

    def _load_stub_fixture(self) -> dict:
        """Load (and cache) the pledge_timeline_spd.json fixture."""
        if self._stub_fixture_cache is not None:
            return self._stub_fixture_cache
        fixture_path = _STUB_FIXTURE_PATH
        if not fixture_path.exists():
            raise FileNotFoundError(
                f"Stub fixture not found at {fixture_path}. "
                "Ensure tests/fixtures/pledge_timeline_spd.json exists (created by plan 03-01)."
            )
        with fixture_path.open("r", encoding="utf-8") as f:
            self._stub_fixture_cache = json.load(f)
        return self._stub_fixture_cache

    # ------------------------------------------------------------------
    # 3. normalize
    # ------------------------------------------------------------------

    def normalize(self, raw: dict) -> list[ChunkRecord]:
        """Map pledge timeline response -> list[ChunkRecord] for embedding.

        Pledges are embedded into Qdrant (not Firestore).
        Pledge fulfillment status is public governmental commitment data, not
        users/{uid} political-opinion data.  The GDPR wall stays on users/ only.

        Chunk text template:
            "Versprechen {claim_id}: {claim_text} | Partei: {party_id} | "
            "Region: {region} | Status (Stand {as_of_date}): {status}\\n"
            "Ereignisse: {event_1_date}: {event_1_description}; ..."

        Payload fields for filtering:
            status      -> PledgeStatus enum value (filterable keyword)
            as_of_date  -> assessment date (filterable datetime)
            claim_id    -> pledge claim identifier (filterable keyword)
            external_id -> None (no monotonic integer ID for pledges)

        Args:
            raw: Dict returned by fetch() — verbatim pledge timeline response.

        Returns:
            list[ChunkRecord] with one entry per pledge item.
        """
        party_id: str = raw["party_id"]
        claim_id: str = raw["claim_id"]
        region: str = raw["region"]
        claim_text: str = raw.get("claim_text") or raw.get("label") or claim_id

        # as_of_date is the run date — never derived from the endpoint.
        as_of_date: date_type = date_type.today()

        # status defaults to IN_PROGRESS (Cambridge endpoint returns no status field).
        raw_status = (raw.get("status") or "").lower()
        try:
            status = PledgeStatus(raw_status)
        except ValueError:
            status = PledgeStatus.IN_PROGRESS  # wahl.chat-side default

        # Build events text from timeline.
        events_parts: list[str] = []
        for ev in raw.get("events", []):
            ev_date = ev.get("date", "")
            ev_desc = ev.get("event") or ev.get("description") or ""
            if ev_date and ev_desc:
                events_parts.append(f"{ev_date}: {ev_desc}")

        events_text = "; ".join(events_parts) if events_parts else "keine Ereignisse verzeichnet"

        # The pledge chunk-text template — German to match the corpus language:
        text = (
            f"Versprechen {claim_id}: {claim_text} | "
            f"Partei: {party_id} | "
            f"Region: {region} | "
            f"Status (Stand {as_of_date.isoformat()}): {status.value}\n"
            f"Ereignisse: {events_text}"
        )

        # Deterministic source_item_id + chunk_key (idempotency).
        external_id_str = f"{party_id}_{claim_id}_{region}"
        source_item_id = compute_source_item_id("pledge_record", external_id_str)
        chunk_key = f"{source_item_id}:0000"

        # Change-aware content_hash (MUST-FIX before live mode): status and
        # as_of_date are embedded in the chunk text, and the point id is stable
        # (source_item_id + chunk_index) — without a content_hash a status/date
        # change would be silently skipped by run.py's already-present guard.
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "text": text,
                    "party_id": party_id,
                    "status": status.value,
                    "as_of_date": as_of_date.isoformat(),
                    "claim_id": claim_id,
                    "region": region,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        return [
            ChunkRecord(
                chunk_key=chunk_key,
                source_item_id=source_item_id,
                chunk_index=0,
                text=text,
                party_id=party_id,
                region=region,
                authority_tier=AuthorityTier.SELF_REPORTED,
                source_type=SourceType.PLEDGE_RECORD,
                publish_date=as_of_date,
                citation_url=None,    # PledgeTracker has no public URL per pledge
                citation_title=f"Versprechen: {claim_id} ({party_id.upper()})",
                # Filterable payload fields:
                external_id=None,     # no monotonic integer ID for pledges
                status=status.value,  # keyword-indexed; str not enum for JSON-safe payload
                as_of_date=as_of_date,
                claim_id=claim_id,
                content_hash=content_hash,
            )
        ]
