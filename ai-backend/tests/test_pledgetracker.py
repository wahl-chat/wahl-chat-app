# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
PledgeTrackerConnector pure unit tests.

Tests defined here:
  - test_pledgetracker_normalize_returns_chunk_records: normalize()
    must return list[ChunkRecord], not SourceItemRecord.
  - test_pledgetracker_normalize_chunk_has_pledge_payload_fields:
    normalized ChunkRecord must carry status, as_of_date, claim_id, and
    external_id=None.

Pledges are embedded (not Firestore-only). This does NOT touch the GDPR Art. 9
wall — pledge status/events are public governmental commitment data, not
users/{uid} political-opinion data.

No Firestore emulator required — the connector is pure Python.
"""

from src.ingestion.connectors.pledgetracker import PledgeTrackerConnector
from src.ingestion.schemas import ChunkRecord, SourceType


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_pledgetracker_normalize_returns_chunk_records() -> None:
    """normalize() must return list[ChunkRecord], not SourceItemRecord."""
    connector = PledgeTrackerConnector(stub=True)
    raw = connector.fetch("spd_mindestlohn-15-euro_DE")
    result = connector.normalize(raw)

    assert isinstance(result, list), "P5-INGEST-04: normalize() must return a list."
    assert len(result) >= 1, "P5-INGEST-04: normalize() must return at least one ChunkRecord."
    assert isinstance(result[0], ChunkRecord), (
        "P5-INGEST-04: normalize() must return ChunkRecord instances, not SourceItemRecord."
    )


def test_pledgetracker_normalize_chunk_has_pledge_payload_fields() -> None:
    """normalized ChunkRecord must carry status, as_of_date, claim_id."""
    connector = PledgeTrackerConnector(stub=True)
    raw = connector.fetch("spd_mindestlohn-15-euro_DE")
    chunks = connector.normalize(raw)

    chunk = chunks[0]
    assert chunk.source_type == SourceType.PLEDGE_RECORD, (
        "P5-INGEST-04: pledge chunk source_type must be PLEDGE_RECORD."
    )
    assert chunk.claim_id is not None, (
        "P5-INGEST-04: pledge chunk must have claim_id set (filterable field, D-05)."
    )
    assert chunk.status is not None, (
        "P5-INGEST-04: pledge chunk must have status set (filterable field, D-05)."
    )
    assert chunk.as_of_date is not None, (
        "P5-INGEST-04: pledge chunk must have as_of_date set (filterable field, D-05)."
    )
    assert chunk.external_id is None, (
        "P5-INGEST-04: pledge chunk external_id must be None (no monotonic int ID, A1/A3)."
    )
    assert "Versprechen" in chunk.text, (
        "P5-INGEST-04: pledge chunk text must follow the German template starting with 'Versprechen'."
    )


def test_pledgetracker_content_hash_present_and_change_sensitive() -> None:
    """(d) Pledge chunks stamp content_hash — status/as_of_date are embedded in
    the chunk text, so a status change MUST re-write via run.py's change-aware
    guard. content_hash must be non-None and sensitive to a status change."""
    connector = PledgeTrackerConnector(stub=True)
    raw = connector.fetch("spd_mindestlohn-15-euro_DE")

    chunk = connector.normalize(raw)[0]
    assert chunk.content_hash is not None, (
        "pledge chunks must stamp content_hash (MUST-FIX before live mode)"
    )

    changed_raw = dict(raw, status="fulfilled")
    changed_chunk = connector.normalize(changed_raw)[0]
    assert changed_chunk.content_hash != chunk.content_hash, (
        "a pledge status change must change content_hash so run.py re-writes it"
    )
