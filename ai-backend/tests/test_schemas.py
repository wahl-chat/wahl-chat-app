# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for ingestion/schemas.py.

Requirements covered:
  - ChunkRecord model — no region_path field; has scalar region
  - ChunkRecord has new optional fields (external_id)
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
    assert chunk.chunk_index == 0, "ChunkRecord.chunk_index should be 0 as provided."


def test_chunk_record_no_region_path():
    """ChunkRecord must NOT have a region_path field."""
    assert "region_path" not in ChunkRecord.model_fields, (
        "ChunkRecord must NOT contain region_path. "
        "Only the scalar 'region' field is allowed to prevent accidentally "
        "storing user-browsing region arrays in Qdrant payload."
    )


def test_chunk_record_has_scalar_region():
    """ChunkRecord must have a scalar 'region' field."""
    assert "region" in ChunkRecord.model_fields, (
        "ChunkRecord must have a scalar 'region' field for MatchAny filtering."
    )


def test_chunk_record_extra_field_rejected():
    """extra='forbid' applies to ChunkRecord."""
    with pytest.raises(ValidationError):
        ChunkRecord(**_valid_chunk_kwargs(), region_path=["EU", "DE"])


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


# =============================================================================
# removed models must not be importable from schemas
# =============================================================================


def test_source_item_record_removed():
    """SourceItemRecord must not exist in ingestion.schemas."""
    import src.ingestion.schemas as s

    assert not hasattr(s, "SourceItemRecord"), (
        "SourceItemRecord must be deleted from schemas.py."
    )


def test_watermark_record_removed():
    """WatermarkRecord must not exist in ingestion.schemas."""
    import src.ingestion.schemas as s

    assert not hasattr(s, "WatermarkRecord"), (
        "WatermarkRecord must be deleted from schemas.py."
    )
