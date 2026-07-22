# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for ingestion/ids.py.

Requirements covered:
  - compute_source_item_id determinism (same inputs → same UUID always)
  - compute_chunk_id returns uuid.UUID (not str) for Qdrant point-id compatibility
  - ID idempotency — re-runs with the same external ID never create duplicate points
  - Embedding constants locked to text-embedding-3-large / 3072 dimensions

These are pure unit tests; no live services required.
"""

import uuid

import pytest

from src.ingestion.ids import (
    WAHL_CHAT_NS,
    compute_chunk_id,
    compute_source_item_id,
    make_chunk_key,
)


def test_source_item_id_determinism():
    """Same source_type + external_id always produces the same UUID."""
    a = compute_source_item_id("party_manifesto", "test-001")
    b = compute_source_item_id("party_manifesto", "test-001")
    assert a == b, (
        "compute_source_item_id must be deterministic: "
        "two calls with identical arguments produced different UUIDs."
    )


def test_source_item_id_different_inputs_differ():
    """Different source_type/external_id combinations must yield different UUIDs."""
    a = compute_source_item_id("party_manifesto", "test-001")
    b = compute_source_item_id("vote_record", "test-001")
    c = compute_source_item_id("party_manifesto", "test-002")
    assert a != b, "compute_source_item_id must differ when source_type differs."
    assert a != c, "compute_source_item_id must differ when external_id differs."


def test_chunk_id_returns_uuid():
    """compute_chunk_id must return uuid.UUID, not a string, for Qdrant point ID."""
    source_item_id = compute_source_item_id("vote_record", "bt-2025-001")
    chunk_id = compute_chunk_id(source_item_id, 3)
    assert isinstance(chunk_id, uuid.UUID), (
        "compute_chunk_id must return uuid.UUID: "
        f"got {type(chunk_id).__name__!r} instead. "
        "Qdrant requires UUID point IDs; string IDs cause type errors at upsert time."
    )


def test_chunk_id_determinism():
    """Same source_item_id + chunk_index always yields the same chunk UUID."""
    source_item_id = compute_source_item_id("party_manifesto", "gp-2025")
    a = compute_chunk_id(source_item_id, 7)
    b = compute_chunk_id(source_item_id, 7)
    assert a == b, (
        "compute_chunk_id must be deterministic: "
        "two calls with identical arguments produced different UUIDs."
    )


def test_make_chunk_key_format():
    """make_chunk_key returns zero-padded '{uuid}:{index:04d}' string."""
    source_item_id = compute_source_item_id("vote_record", "bt-2025-999")
    key = make_chunk_key(source_item_id, 3)
    # Format: <uuid>:0003
    parts = key.rsplit(":", 1)
    assert len(parts) == 2, (
        "make_chunk_key must produce exactly one colon separator between UUID and index."
    )
    uuid_part, index_part = parts
    # Validate UUID part
    try:
        uuid.UUID(uuid_part)
    except ValueError:
        pytest.fail(f"make_chunk_key UUID portion is not a valid UUID: {uuid_part!r}")
    # Validate zero-padded index
    assert index_part == "0003", (
        f"make_chunk_key must zero-pad the chunk index to 4 digits: "
        f"expected '0003', got {index_part!r}."
    )


def test_wahl_chat_ns_is_uuid():
    """WAHL_CHAT_NS must be a committed uuid.UUID constant."""
    assert isinstance(WAHL_CHAT_NS, uuid.UUID), (
        "WAHL_CHAT_NS must be a uuid.UUID instance. "
        "It must never be changed after first production use — changing it shifts "
        "all corpus IDs and breaks idempotency."
    )


def test_embedding_guard():
    """Embedding constants must be text-embedding-3-large / 3072 dimensions.

    setup_collection.py exports EMBEDDING_DIM and EMBEDDING_MODEL.
    This test uses pytest.importorskip so it skips gracefully until the
    module and its constants exist.
    """
    setup = pytest.importorskip(
        "src.ingestion.setup_collection",
        reason="setup_collection.py is not yet created — test tightens once it lands",
    )
    dim = getattr(setup, "EMBEDDING_DIM", None)
    model = getattr(setup, "EMBEDDING_MODEL", None)
    assert dim == 3072, (
        f"EMBEDDING_DIM must be 3072 for text-embedding-3-large: got {dim!r}."
    )
    assert model == "text-embedding-3-large", (
        f"EMBEDDING_MODEL must be 'text-embedding-3-large': got {model!r}."
    )
