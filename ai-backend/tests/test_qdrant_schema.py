# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Qdrant collection schema tests.

These tests exercise the local Qdrant instance (started via
``docker compose up -d qdrant`` or ``make stores-up``) and verify:

  - A single ``wahlchat_chunks_dev`` collection exists after
    calling ``setup_collection.setup()``.
  - All eleven required payload indexes are present
    (party_id, region, region_path, authority_tier, source_type,
    publish_date, source_item_id, external_id, status, as_of_date, claim_id)
    as returned by ``get_collection()``.
  - MatchAny filter on scalar ``region`` returns chunks
    whose region value is in the election's region_path list and
    EXCLUDES chunks whose region is NOT in that list.
  - Upserting the same ``compute_chunk_id``-derived UUID twice
    leaves the point count unchanged (overwrite, not duplicate).

All tests skip gracefully when local Qdrant is not reachable — they
require no live API keys, no Firebase service, and no real data.

Isolation: throwaway points are written to a uniquely-named
temporary collection that is deleted in a ``finally`` block, preserving
the guarantee that ``wahlchat_chunks_dev`` contains zero chunks.
"""

import uuid
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Module-level Qdrant reachability guard.
#
# IMPORTANT: conftest.py patches ``qdrant_client.QdrantClient`` at module
# level so that src.vector_store_helper can be imported without hitting a
# live Qdrant server.  That patch is applied BEFORE this test module is
# imported — which would cause the fixture-created client to be a MagicMock.
#
# We work around this by capturing the real QdrantClient class from the
# ``qdrant_client._client`` submodule BEFORE conftest's patch can shadow the
# symbol on ``qdrant_client``.  ``qdrant_client._client.QdrantClient`` is
# the concrete implementation class and is NOT patched by conftest (conftest
# patches the re-export at ``qdrant_client.QdrantClient``).
# ---------------------------------------------------------------------------
from qdrant_client.qdrant_client import QdrantClient as _RealQdrantClient
from qdrant_client import models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    VectorParams,
)

from src.ingestion.ids import compute_chunk_id, compute_source_item_id
from src.ingestion.setup_collection import (
    COLLECTION_NAME,
    EMBEDDING_DIM,
    _REQUIRED_INDEXES,
    setup,
)

_QDRANT_URL = "http://localhost:6333"


def _new_real_client() -> _RealQdrantClient:
    """Return an unpatched QdrantClient pointing at local Qdrant."""
    return _RealQdrantClient(url=_QDRANT_URL, api_key=None)


def _qdrant_reachable() -> bool:
    """Return True if local Qdrant responds to list_collections."""
    try:
        _new_real_client().get_collections()
        return True
    except Exception:  # noqa: BLE001
        return False


if not _qdrant_reachable():
    pytest.skip(
        "local Qdrant not reachable — run `make stores-up` or "
        "`docker compose up -d qdrant` before executing these tests",
        allow_module_level=True,
    )

# Type alias used in annotations throughout — same interface as QdrantClient.
QdrantClient = _RealQdrantClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qdrant() -> QdrantClient:
    """Module-scoped real Qdrant client for schema tests."""
    return _new_real_client()


@pytest.fixture(scope="module", autouse=True)
def ensure_collection(qdrant: QdrantClient) -> None:
    """Ensure ``wahlchat_chunks_dev`` exists before any test runs."""
    setup(client=qdrant)


@pytest.fixture()
def temp_collection(qdrant: QdrantClient) -> Generator[str, None, None]:
    """Create an isolated throwaway collection mirroring the V2 config.

    Yielded value is the temporary collection name.  The collection is
    deleted in a finally block so no throwaway data leaks into the main
    collection and the zero-chunk guarantee on wahlchat_chunks_dev is
    preserved.
    """
    name = f"_test_tmp_{uuid.uuid4().hex[:8]}"
    qdrant.create_collection(
        collection_name=name,
        vectors_config={"dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)},
    )
    # Create the region index so MatchAny filter works in the temp collection.
    qdrant.create_payload_index(
        collection_name=name,
        field_name="region",
        field_schema=models.PayloadSchemaType.KEYWORD,
        wait=True,
    )
    try:
        yield name
    finally:
        try:
            qdrant.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass  # best-effort cleanup


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_collection_exists(qdrant: QdrantClient) -> None:
    """wahlchat_chunks_dev must exist after setup().

    setup() is called by the autouse fixture before this test runs.
    """
    collection_names = [c.name for c in qdrant.get_collections().collections]
    assert COLLECTION_NAME in collection_names, (
        f"collection '{COLLECTION_NAME}' not found in Qdrant after "
        f"calling setup(). Found: {collection_names!r}. "
        "Run `uv run python -m src.ingestion.setup_collection` to create it."
    )


def test_payload_indexes(qdrant: QdrantClient) -> None:
    """all eleven required payload indexes must be present.

    The eleven indexes are: party_id, region, region_path, authority_tier,
    source_type, publish_date, source_item_id, external_id, status,
    as_of_date, claim_id.  Missing any breaks the per-tenant HNSW
    optimisation, cross-level MatchAny queries, or the cursor.
    """
    info = qdrant.get_collection(COLLECTION_NAME)
    indexed = set(info.payload_schema.keys())
    missing = _REQUIRED_INDEXES - indexed
    assert not missing, (
        f"missing payload indexes in '{COLLECTION_NAME}': {missing!r}. "
        "Expected all of: {_REQUIRED_INDEXES!r}. "
        "Re-run `uv run python -m src.ingestion.setup_collection` to add them."
    )
    assert indexed.issuperset(_REQUIRED_INDEXES), (
        f"payload_schema does not cover all required indexes. "
        f"indexed={indexed!r}, required={_REQUIRED_INDEXES!r}"
    )


def test_match_any_filter(qdrant: QdrantClient, temp_collection: str) -> None:
    """MatchAny on scalar region must include DE and exclude DE-BY.

    Election region_path for Rhineland-Palatinate: ["EU", "DE", "DE-RP"].
    A chunk with region="DE" is in that path → MUST be returned.
    A chunk with region="DE-BY" (Bavaria) is NOT in that path → MUST be excluded.

    This test proves the scalar-region filter direction is correct and will
    surface correctly at query time in the connectors.
    """
    election_region_path = ["EU", "DE", "DE-RP"]
    dummy_vector = [0.0] * EMBEDDING_DIM

    # Two deterministic point IDs — one for each test chunk.
    source_id = compute_source_item_id("party_manifesto", "sc2-test-source-001")
    point_id_de = compute_chunk_id(source_id, 0)
    point_id_de_by = compute_chunk_id(source_id, 1)

    qdrant.upsert(
        collection_name=temp_collection,
        points=[
            PointStruct(
                id=str(point_id_de),
                vector={"dense": dummy_vector},
                payload={"region": "DE", "party_id": "spd"},
            ),
            PointStruct(
                id=str(point_id_de_by),
                vector={"dense": dummy_vector},
                payload={"region": "DE-BY", "party_id": "csu"},
            ),
        ],
        wait=True,
    )

    region_filter = Filter(
        must=[
            FieldCondition(
                key="region",
                match=MatchAny(any=election_region_path),
            )
        ]
    )

    results = qdrant.scroll(
        collection_name=temp_collection,
        scroll_filter=region_filter,
        limit=100,
        with_payload=True,
    )
    returned_ids = {str(pt.id) for pt in results[0]}

    assert str(point_id_de) in returned_ids, (
        "chunk with region='DE' must be returned when election "
        f"region_path={election_region_path!r} — 'DE' is a member of that path. "
        f"Returned IDs: {returned_ids!r}"
    )
    assert str(point_id_de_by) not in returned_ids, (
        "chunk with region='DE-BY' must NOT be returned when election "
        f"region_path={election_region_path!r} — 'DE-BY' is not a member of that path. "
        "If this assertion fails, wrong-region documents would leak into Rhineland-Palatinate "
        "query results at runtime (information disclosure). "
        f"Returned IDs: {returned_ids!r}"
    )


def test_idempotent_upsert(qdrant: QdrantClient, temp_collection: str) -> None:
    """upserting the same UUID point twice must not increase point count.

    Qdrant upsert semantics: if a point with the same ID already exists,
    the existing point is overwritten (not duplicated).  This test asserts
    that property so connectors can safely re-run ingestion without bloating
    the collection.
    """
    dummy_vector = [0.0] * EMBEDDING_DIM
    source_id = compute_source_item_id("party_manifesto", "vec04-test-source-001")
    point_id = compute_chunk_id(source_id, 0)

    payload_v1 = {"region": "DE", "party_id": "spd", "text": "version-one"}
    payload_v2 = {"region": "DE", "party_id": "spd", "text": "version-two"}

    def _upsert(payload: dict) -> None:
        qdrant.upsert(
            collection_name=temp_collection,
            points=[
                PointStruct(
                    id=str(point_id),
                    vector={"dense": dummy_vector},
                    payload=payload,
                )
            ],
            wait=True,
        )

    def _count() -> int:
        info = qdrant.get_collection(temp_collection)
        return info.points_count

    _upsert(payload_v1)
    count_after_first = _count()

    _upsert(payload_v2)
    count_after_second = _count()

    assert count_after_first == count_after_second, (
        "point count must not increase when the same UUID is upserted twice. "
        f"After first upsert: {count_after_first}; after second upsert: {count_after_second}. "
        "Qdrant should overwrite the existing point, not duplicate it. "
        "If this fails, connectors that re-run ingestion will bloat the collection."
    )

    # Verify the payload WAS updated (overwrite semantics, not a no-op).
    fetched = qdrant.retrieve(
        collection_name=temp_collection,
        ids=[str(point_id)],
        with_payload=True,
    )
    assert fetched and fetched[0].payload is not None, (
        "could not retrieve the upserted point — something went wrong."
    )
    assert fetched[0].payload.get("text") == "version-two", (
        "second upsert should have overwritten the payload with 'version-two'. "
        f"Actual payload: {fetched[0].payload!r}"
    )


def test_new_phase5_indexes_present(qdrant: QdrantClient) -> None:
    """all four new payload indexes must be present after setup().

    The four new indexes are: external_id (IntegerIndexParams with range=True),
    status (keyword), as_of_date (datetime), claim_id (keyword).
    Missing external_id range index breaks the order_by DESC cursor query.
    """
    _PHASE5_INDEXES = {"external_id", "status", "as_of_date", "claim_id"}

    info = qdrant.get_collection(COLLECTION_NAME)
    indexed = set(info.payload_schema.keys())
    missing = _PHASE5_INDEXES - indexed
    assert not missing, (
        f"missing payload indexes in '{COLLECTION_NAME}': {missing!r}. "
        "Re-run `uv run python -m src.ingestion.setup_collection` to add them. "
        "Note: external_id must use IntegerIndexParams(range=True) for the cursor query."
    )
