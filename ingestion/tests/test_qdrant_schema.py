# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Qdrant collection schema tests.

These tests exercise the local Qdrant instance (started via
``docker compose up -d qdrant`` or ``make stores-up``) and verify:

  - ``setup_collection.setup()`` creates the collection, every payload index
    in the canonical ``_REQUIRED_INDEXES`` spec, and the embedding-space
    fingerprint; a re-run verifies instead of re-stamping.
  - MatchAny filter on scalar ``region`` returns chunks
    whose region value is in the election's region_path list and
    EXCLUDES chunks whose region is NOT in that list.
  - Upserting the same ``compute_chunk_id``-derived UUID twice
    leaves the point count unchanged (overwrite, not duplicate).

When local Qdrant is not reachable these tests skip during local runs but
HARD-FAIL under CI (``CI`` env set), where a Qdrant service is always
provisioned — so the schema is verified on every CI run, never silently
skipped. They require no live API keys, no Firebase service, and no real data.

Isolation: EVERYTHING here runs against uniquely-named throwaway collections
deleted afterwards — setup() included (COLLECTION_NAME is swapped for the
module). A developer's local ``wahlchat_chunks_dev`` corpus is never read,
written, or fingerprint-stamped by the test suite.
"""

import os
import uuid
from typing import Generator

import pytest

# ---------------------------------------------------------------------------
# Module-level Qdrant reachability guard.
#
# IMPORTANT: conftest.py patches ``qdrant_client.QdrantClient`` at module
# level so that modules constructing a client at import time can be imported
# without hitting a
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

import ingestion.setup_collection as setup_collection
from ingestion.ids import compute_chunk_id, compute_source_item_id
from ingestion.setup_collection import (
    EMBEDDING_DIM,
    _REQUIRED_INDEXES,
    expected_fingerprint,
    read_fingerprint,
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
    _unreachable_msg = (
        "local Qdrant not reachable — run `make stores-up` or "
        "`docker compose up -d qdrant` before executing these tests"
    )
    # CI provisions a Qdrant service, so unreachability there is a real failure
    # to surface — not a reason to silently drop schema coverage. Locally (no CI
    # env) keep skipping so `make test-backend` runs without stores up.
    if os.getenv("CI"):
        raise RuntimeError(f"{_unreachable_msg} (CI must provision Qdrant)")
    pytest.skip(_unreachable_msg, allow_module_level=True)

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
def schema_collection(qdrant: QdrantClient) -> Generator[str, None, None]:
    """Run setup() against an ISOLATED throwaway collection.

    COLLECTION_NAME is swapped for the whole module so setup() (and its
    fingerprint stamping) never touches a developer's real local corpus —
    a populated legacy store would otherwise be refused (no fingerprint) or,
    worse, adopted with whatever env the test run happens to have.
    """
    name = f"_test_schema_{uuid.uuid4().hex[:8]}"
    original = setup_collection.COLLECTION_NAME
    setup_collection.COLLECTION_NAME = name
    try:
        setup(client=qdrant)
        yield name
    finally:
        setup_collection.COLLECTION_NAME = original
        try:
            qdrant.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass  # best-effort cleanup


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
        vectors_config={
            "dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
        },
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


def test_collection_exists(qdrant: QdrantClient, schema_collection: str) -> None:
    """The collection must exist after setup().

    setup() is called by the autouse fixture before this test runs.
    """
    collection_names = [c.name for c in qdrant.get_collections().collections]
    assert schema_collection in collection_names, (
        f"collection '{schema_collection}' not found in Qdrant after "
        f"calling setup(). Found: {collection_names!r}. "
        "Run `uv run python -m ingestion.setup_collection` to create it."
    )


def test_fingerprint_stamped_and_stable(
    qdrant: QdrantClient, schema_collection: str
) -> None:
    """setup() stamps the embedding-space fingerprint; a re-run verifies it.

    The fingerprint records provider/model/dim so a config pointing at a
    different vector space is refused instead of silently mixing embeddings.
    """
    stored = read_fingerprint(qdrant, schema_collection)
    assert stored is not None, "setup() must stamp a fingerprint on creation"
    expected = expected_fingerprint()
    for key in ("embedding_provider", "embedding_model", "embedding_dim"):
        assert stored.get(key) == expected[key], (
            f"fingerprint field {key!r} mismatch: stored={stored.get(key)!r} "
            f"expected={expected[key]!r}"
        )
    # Idempotent re-run: verifies the existing fingerprint, no error.
    setup(client=qdrant)
    # corpus_point_count must NOT count the fingerprint sentinel.
    assert setup_collection.corpus_point_count(qdrant) == 0, (
        "a collection holding only the fingerprint sentinel must read as empty "
        "(the corpus rollout gate keys on corpus_point_count() > 0)"
    )


def test_payload_indexes(qdrant: QdrantClient, schema_collection: str) -> None:
    """Every canonical payload index (``_REQUIRED_INDEXES``) must be present.

    Asserted against the single source of truth in ``setup_collection`` rather
    than a hard-coded list, so the test can never drift from the schema. Missing
    any index breaks the per-tenant HNSW optimisation, cross-level MatchAny
    queries, or the cursor.
    """
    info = qdrant.get_collection(schema_collection)
    indexed = set(info.payload_schema.keys())
    missing = _REQUIRED_INDEXES - indexed
    assert not missing, (
        f"missing payload indexes in '{schema_collection}': {missing!r}. "
        "Expected all of: {_REQUIRED_INDEXES!r}. "
        "Re-run `uv run python -m ingestion.setup_collection` to add them."
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
