# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for ingestion/schemas.py.

Requirements covered:
  - ChunkRecord model — no region_path field; has scalar region
  - ChunkRecord has new optional fields (external_id, status, as_of_date, claim_id)
  - SourceItemRecord and WatermarkRecord removed from schemas.py

These are pure unit tests; no live services required.
"""

from datetime import date

import pytest
from pydantic import ValidationError

from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import (
    AuthorityTier,
    ChunkRecord,
    PledgeStatus,
    SourceType,
)


# =============================================================================
# Helpers
# =============================================================================

_TODAY = date.today()
_SOURCE_ITEM_ID = compute_source_item_id("party_manifesto", "test-fixture-001")


def _valid_chunk_kwargs() -> dict:
    return dict(
        chunk_key=f"{_SOURCE_ITEM_ID}:0000",
        source_item_id=_SOURCE_ITEM_ID,
        chunk_index=0,
        text="Wir wollen mehr Klimaschutz.",
        party_id="spd",
        region="DE",
        authority_tier=AuthorityTier.AUTHORITATIVE,
        source_type=SourceType.PARTY_MANIFESTO,
        publish_date=_TODAY,
        external_id=None,
    )


# =============================================================================
# ChunkRecord
# =============================================================================


def test_chunk_record_valid():
    """ChunkRecord constructs from valid required fields."""
    chunk = ChunkRecord(**_valid_chunk_kwargs())
    assert chunk.chunk_index == 0, (
        "DATA-02: ChunkRecord.chunk_index should be 0 as provided."
    )


def test_chunk_record_no_region_path():
    """ChunkRecord must NOT have a region_path field."""
    assert "region_path" not in ChunkRecord.model_fields, (
        "DATA-02/D-07: ChunkRecord must NOT contain region_path. "
        "Only the scalar 'region' field is allowed to prevent accidentally "
        "storing user-browsing region arrays in Qdrant payload (T-02-03)."
    )


def test_chunk_record_has_scalar_region():
    """ChunkRecord must have a scalar 'region' field."""
    assert "region" in ChunkRecord.model_fields, (
        "DATA-02/D-07: ChunkRecord must have a scalar 'region' field for MatchAny filtering."
    )


def test_chunk_record_extra_field_rejected():
    """extra='forbid' applies to ChunkRecord."""
    with pytest.raises(ValidationError):
        ChunkRecord(**_valid_chunk_kwargs(), region_path=["EU", "DE"])


# =============================================================================
# PledgeStatus
# =============================================================================


def test_pledge_status_values():
    """PledgeStatus enum has exactly the six specified values."""
    expected = {"fulfilled", "partially_fulfilled", "in_progress", "broken", "stalled", "not_yet_started"}
    actual = {s.value for s in PledgeStatus}
    assert actual == expected, (
        f"D-04: PledgeStatus must have exactly these values: {expected}. "
        f"Got: {actual}."
    )


# =============================================================================
# ChunkRecord optional fields
# =============================================================================


def test_chunk_record_has_external_id():
    """ChunkRecord must have optional external_id (int) field."""
    assert "external_id" in ChunkRecord.model_fields
    kwargs = _valid_chunk_kwargs()
    kwargs["external_id"] = 3602
    chunk = ChunkRecord(**kwargs)
    assert chunk.external_id == 3602


def test_chunk_record_external_id_optional():
    """ChunkRecord.external_id defaults to None."""
    chunk = ChunkRecord(**_valid_chunk_kwargs())
    assert chunk.external_id is None


def test_chunk_record_has_status():
    """ChunkRecord must have optional status field."""
    assert "status" in ChunkRecord.model_fields


def test_chunk_record_has_as_of_date():
    """ChunkRecord must have optional as_of_date field."""
    assert "as_of_date" in ChunkRecord.model_fields


def test_chunk_record_has_claim_id():
    """ChunkRecord must have optional claim_id field."""
    assert "claim_id" in ChunkRecord.model_fields


def test_chunk_record_pledge_fields_default_none():
    """ChunkRecord status/as_of_date/claim_id default to None."""
    chunk = ChunkRecord(**_valid_chunk_kwargs())
    assert chunk.status is None
    assert chunk.as_of_date is None
    assert chunk.claim_id is None


# =============================================================================
# removed models must not be importable from schemas
# =============================================================================


def test_source_item_record_removed():
    """SourceItemRecord must not exist in ingestion.schemas."""
    import src.ingestion.schemas as s
    assert not hasattr(s, "SourceItemRecord"), (
        "P5-DATA-02: SourceItemRecord must be deleted from schemas.py."
    )


def test_watermark_record_removed():
    """WatermarkRecord must not exist in ingestion.schemas."""
    import src.ingestion.schemas as s
    assert not hasattr(s, "WatermarkRecord"), (
        "P5-DATA-02: WatermarkRecord must be deleted from schemas.py."
    )


def test_source_type_has_pledge_record():
    """SourceType enum must include PLEDGE_RECORD."""
    from src.ingestion.schemas import SourceType
    assert "pledge_record" in {s.value for s in SourceType}, (
        "P5-DATA-01: SourceType must include PLEDGE_RECORD = 'pledge_record'."
    )
