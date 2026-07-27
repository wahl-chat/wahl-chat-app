# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Retrieve capability source_type filter.

Tests defined here:
  - test_source_type_filter: retrieve(query, source_type='vote_record') returns
    only payloads with source_type == 'vote_record'.

Verification strategy (no live OpenAI needed):
  1. Seed the temp collection with mock points — vote_record, party_manifesto, qa_transcript.
  2. Call retrieve() with a deterministic fake embed callable so no real API key is needed.
  3. Assert every returned payload has source_type == 'vote_record'.
  4. Assert party_manifesto / qa_transcript points are excluded.

This does NOT require a live Gemini call — retrieve() is called directly and the
embed callable is injected via the _embed_fn override.
"""

import uuid

import pytest

# ---------------------------------------------------------------------------
# Module-level Qdrant reachability guard.
# ---------------------------------------------------------------------------
try:
    from qdrant_client.qdrant_client import QdrantClient as _RealQdrantClient

    _client = _RealQdrantClient(url="http://localhost:6333", api_key=None)
    _client.get_collections()
    _QDRANT_UP = True
except Exception:  # noqa: BLE001
    _QDRANT_UP = False

if not _QDRANT_UP:
    pytest.skip(
        "local Qdrant not reachable — run `make stores-up` or "
        "`docker compose up -d qdrant` before executing these tests",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMBEDDING_DIM = 3072  # must match setup_collection.EMBEDDING_DIM


def _zero_vector() -> list[float]:
    """Return a deterministic all-zero embedding vector for seeding test points.

    A zero vector is valid for cosine-similarity search; Qdrant returns all seeded
    points when the query is also zero (cosine undefined → fallback ordering).
    The test asserts on *filter* correctness, not score ranking.
    """
    return [0.0] * _EMBEDDING_DIM


def _fake_embed(query: str) -> list[float]:  # noqa: ARG001
    """Deterministic embed callable injected via _embed_fn — no OpenAI API key needed."""
    return _zero_vector()


def _make_payload(source_type: str, party_id: str = "spd") -> dict:
    """Build a minimal ChunkRecord-shaped payload for a test point."""
    return {
        "source_type": source_type,
        "party_id": party_id,
        "region": "DE",
        "authority_tier": "factual_record",
        "publish_date": "2024-01-15T00:00:00",
        "text": f"Test chunk with source_type={source_type}",
        "chunk_index": 0,
        "source_item_id": str(uuid.uuid4()),
        "chunk_key": f"{uuid.uuid4()}:0000",
        "citation_url": None,
        "citation_title": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_source_type_filter(temp_qdrant_collection) -> None:  # type: ignore[type-arg]
    """retrieve(query, source_type='vote_record') returns only vote_record payloads.

    Verification:
    1. Seed the temp collection with 3 source types: vote_record (×3), party_manifesto (×2),
       qa_transcript (×1).
    2. Call retrieve() directly with _embed_fn=_fake_embed so no live OpenAI key is needed.
    3. Override _client to point at the throwaway temp collection.
    4. Assert ALL returned payloads have source_type == 'vote_record'.
    5. Assert no manifesto or Q&A chunks are in the result.

    This is the source-relevance filter correctness guarantee: the MatchValue filter
    on source_type must gate retrieval to the requested content category.
    """
    from qdrant_client.models import PointStruct

    from src.ingestion.retrieve import retrieve

    client, collection_name = temp_qdrant_collection

    # ------------------------------------------------------------------
    # The temp collection was created by conftest with vector size=3072
    # and named vector "dense" — matches setup_collection constants.
    # ------------------------------------------------------------------

    # Seed: 3 vote_record, 2 party_manifesto, 1 qa_transcript
    points = []
    source_types = [
        "vote_record",
        "vote_record",
        "vote_record",
        "party_manifesto",
        "party_manifesto",
        "qa_transcript",
    ]
    for i, st in enumerate(source_types):
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": _zero_vector()},
                payload=_make_payload(st),
            )
        )

    client.upsert(collection_name=collection_name, points=points, wait=True)

    # ------------------------------------------------------------------
    # Monkey-patch COLLECTION_NAME to point at our temp collection.
    # We achieve this by passing _client and the collection override
    # via a wrapper: retrieve() uses _client kwarg but reads COLLECTION_NAME
    # from the module. We wrap by temporarily monkeypatching the module constant.
    # ------------------------------------------------------------------
    import src.ingestion.retrieve as _retrieve_mod

    original_collection = _retrieve_mod.COLLECTION_NAME
    _retrieve_mod.COLLECTION_NAME = collection_name  # type: ignore[assignment]

    try:
        results = retrieve(
            query="mindestlohn vote record",
            source_type="vote_record",
            limit=10,
            _client=client,
            _embed_fn=_fake_embed,
        )
    finally:
        _retrieve_mod.COLLECTION_NAME = original_collection  # type: ignore[assignment]

    # ------------------------------------------------------------------
    # Assertion: every returned payload must be vote_record.
    # ------------------------------------------------------------------
    assert len(results) > 0, (
        "retrieve(source_type='vote_record') returned no results — "
        "expected 3 seeded vote_record chunks"
    )

    for payload in results:
        assert payload.get("source_type") == "vote_record", (
            f"retrieve(source_type='vote_record') must return ONLY "
            f"vote_record payloads — got source_type={payload.get('source_type')!r}. "
            f"Full payload: {payload!r}"
        )

    # Confirm party_manifesto and qa_transcript are NOT present.
    returned_types = {p.get("source_type") for p in results}
    assert "party_manifesto" not in returned_types, (
        "party_manifesto chunks must be excluded when source_type='vote_record'"
    )
    assert "qa_transcript" not in returned_types, (
        "qa_transcript chunks must be excluded when source_type='vote_record'"
    )

    # Confirm all 3 vote_record chunks are returned (no false negatives).
    assert len(results) == 3, (
        f"expected exactly 3 vote_record chunks, got {len(results)}"
    )


# ---------------------------------------------------------------------------
# test_query_vector_skips_embed
# ---------------------------------------------------------------------------


def test_query_vector_skips_embed(temp_qdrant_collection) -> None:  # type: ignore[type-arg]
    """When query_vector is supplied, retrieve() must NOT call the embed function.

    Verification:
    1. Create a sentinel embed callable that raises RuntimeError if called.
    2. Seed the temp collection with one vote_record point (zero vector).
    3. Call retrieve(query_vector=<zero_vector>, source_type='vote_record', ...).
    4. Assert embed sentinel was never invoked (RuntimeError would surface if it were).
    5. Assert at least one result is returned (the zero-vector query finds the seeded point).
    """
    from qdrant_client.models import PointStruct

    from src.ingestion.retrieve import retrieve

    client, collection_name = temp_qdrant_collection

    # Seed one vote_record point with party_id so the selective filter is satisfied.
    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": _zero_vector()},
                payload=_make_payload("vote_record"),
            )
        ],
        wait=True,
    )

    # Sentinel embed that raises if called — proves embed is skipped.
    def _sentinel_embed(query: str) -> list[float]:  # noqa: ARG001
        raise RuntimeError("retrieve() called embed when query_vector was supplied!")

    import src.ingestion.retrieve as _retrieve_mod

    original_collection = _retrieve_mod.COLLECTION_NAME
    _retrieve_mod.COLLECTION_NAME = collection_name  # type: ignore[assignment]

    try:
        results = retrieve(
            query="any query — should be ignored",
            query_vector=_zero_vector(),
            source_type="vote_record",
            limit=5,
            _client=client,
            _embed_fn=_sentinel_embed,  # Would raise if called
        )
    finally:
        _retrieve_mod.COLLECTION_NAME = original_collection  # type: ignore[assignment]

    # If sentinel was called, RuntimeError would have surfaced above.
    assert len(results) >= 1, (
        "retrieve(query_vector=...) returned no results — "
        "expected at least 1 seeded vote_record chunk"
    )


# ---------------------------------------------------------------------------
# test_empty_filter_rejected
# ---------------------------------------------------------------------------


def test_empty_filter_rejected() -> None:
    """retrieve() with no selective filter (no party_id, party_ids_contains, source_type)
    must raise ValueError BEFORE calling the embed function or query_points.

    The m=0 / payload_m=16 tenant-only HNSW design means Filter(must=[]) would
    brute-force the entire corpus — this MUST be rejected.

    Verification:
    1. Create a sentinel embed that raises RuntimeError if called.
    2. Create a fake client whose query_points raises RuntimeError if called.
    3. Call retrieve(query, region_path=['DE']) — region alone is NOT selective.
    4. Assert ValueError is raised.
    5. Because ValueError is raised before any embed/query_points call, the sentinels
       are never triggered (both would surface as RuntimeError if hit, which would fail
       the pytest.raises(ValueError) guard and be visible in the traceback).
    """
    from src.ingestion.retrieve import retrieve

    def _sentinel_embed(query: str) -> list[float]:  # noqa: ARG001
        raise RuntimeError("embed was called before empty-filter rejection!")

    class _SentinelClient:
        def query_points(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise RuntimeError("query_points was called before empty-filter rejection!")

    # Only region_path supplied — NOT selective.
    import pytest as _pytest

    with _pytest.raises(ValueError, match="selective"):
        retrieve(
            query="test query",
            region_path=["DE"],
            _client=_SentinelClient(),  # type: ignore[arg-type]
            _embed_fn=_sentinel_embed,
        )


# ---------------------------------------------------------------------------
# test_selective_source_type_allowed
# ---------------------------------------------------------------------------


def test_selective_source_type_allowed(temp_qdrant_collection) -> None:  # type: ignore[type-arg]
    """source_type alone IS a selective filter — must NOT raise ValueError.

    Verification:
    1. Seed the temp collection with one vote_record point.
    2. Call retrieve(query, source_type='vote_record') — no party_id supplied.
    3. Assert no ValueError is raised.
    4. Assert results are returned (the seeded point is found).
    """
    from qdrant_client.models import PointStruct

    from src.ingestion.retrieve import retrieve

    client, collection_name = temp_qdrant_collection

    client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": _zero_vector()},
                payload=_make_payload("vote_record"),
            )
        ],
        wait=True,
    )

    import src.ingestion.retrieve as _retrieve_mod

    original_collection = _retrieve_mod.COLLECTION_NAME
    _retrieve_mod.COLLECTION_NAME = collection_name  # type: ignore[assignment]

    try:
        # Must NOT raise — selective source_type is always valid.
        results = retrieve(
            query="any query",
            source_type="vote_record",
            limit=5,
            _client=client,
            _embed_fn=_fake_embed,
        )
    finally:
        _retrieve_mod.COLLECTION_NAME = original_collection  # type: ignore[assignment]

    assert len(results) >= 1, (
        "retrieve(source_type='vote_record') returned no results — "
        "expected at least 1 seeded chunk"
    )


# ---------------------------------------------------------------------------
# legislature_period_id filter tests
# ---------------------------------------------------------------------------


def _make_payload_with_period(
    source_type: str,
    party_ids: list[str] | None = None,
    legislature_period_id: int | None = None,
) -> dict:
    """Build a payload that includes legislature_period_id for period-filter tests."""
    base: dict = {
        "source_type": source_type,
        "party_id": (party_ids[0] if party_ids else "spd"),
        "party_ids": party_ids or ["spd"],
        "region": "DE",
        "authority_tier": "factual_record",
        "publish_date": "2024-01-15T00:00:00",
        "text": f"Test chunk source_type={source_type} period={legislature_period_id}",
        "chunk_index": 0,
        "source_item_id": str(uuid.uuid4()),
        "chunk_key": f"{uuid.uuid4()}:0000",
        "citation_url": None,
        "citation_title": None,
    }
    if legislature_period_id is not None:
        base["legislature_period_id"] = legislature_period_id
    return base


def test_legislature_period_id_filter(temp_qdrant_collection) -> None:  # type: ignore[type-arg]
    """retrieve(legislature_period_id=149) returns only chunks matching that period.

    Verification:
    1. Seed 2 vote_record chunks with legislature_period_id=149 (Bayern).
    2. Seed 2 vote_record chunks with legislature_period_id=161 (Bundestag).
    3. Call retrieve(party_ids_contains='csu', source_type='vote_record',
                     legislature_period_id=149).
    4. Assert only the 2 period-149 chunks are returned (period filter applied).
    """
    from qdrant_client.models import PointStruct

    from src.ingestion.retrieve import retrieve

    client, collection_name = temp_qdrant_collection

    # Seed: 2 chunks period 149, 2 chunks period 161 — all for party "csu".
    points = []
    for period_id in [149, 149, 161, 161]:
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": _zero_vector()},
                payload=_make_payload_with_period(
                    "vote_record",
                    party_ids=["csu"],
                    legislature_period_id=period_id,
                ),
            )
        )
    client.upsert(collection_name=collection_name, points=points, wait=True)

    import src.ingestion.retrieve as _retrieve_mod

    original_collection = _retrieve_mod.COLLECTION_NAME
    _retrieve_mod.COLLECTION_NAME = collection_name  # type: ignore[assignment]
    try:
        results = retrieve(
            query="Bayern vote",
            source_type="vote_record",
            party_ids_contains="csu",
            legislature_period_id=149,
            limit=10,
            _client=client,
            _embed_fn=_fake_embed,
        )
    finally:
        _retrieve_mod.COLLECTION_NAME = original_collection  # type: ignore[assignment]

    assert len(results) == 2, (
        f"expected exactly 2 period-149 chunks; got {len(results)}. "
        "legislature_period_id filter is not narrowing results correctly."
    )
    for payload in results:
        assert payload.get("legislature_period_id") == 149, (
            f"expected legislature_period_id=149, got {payload.get('legislature_period_id')!r}"
        )


def test_legislature_period_id_filter_absent_when_none(temp_qdrant_collection) -> None:  # type: ignore[type-arg]
    """retrieve(legislature_period_id=None) adds no period filter — all periods returned.

    Verification:
    1. Seed 2 vote_record chunks with period 149 and 2 with period 161.
    2. Call retrieve(party_ids_contains='csu', source_type='vote_record') (no period).
    3. Assert all 4 chunks are returned (no period narrowing).
    """
    from qdrant_client.models import PointStruct

    from src.ingestion.retrieve import retrieve

    client, collection_name = temp_qdrant_collection

    points = []
    for period_id in [149, 149, 161, 161]:
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={"dense": _zero_vector()},
                payload=_make_payload_with_period(
                    "vote_record",
                    party_ids=["csu"],
                    legislature_period_id=period_id,
                ),
            )
        )
    client.upsert(collection_name=collection_name, points=points, wait=True)

    import src.ingestion.retrieve as _retrieve_mod

    original_collection = _retrieve_mod.COLLECTION_NAME
    _retrieve_mod.COLLECTION_NAME = collection_name  # type: ignore[assignment]
    try:
        results = retrieve(
            query="Bayern vote",
            source_type="vote_record",
            party_ids_contains="csu",
            legislature_period_id=None,
            limit=10,
            _client=client,
            _embed_fn=_fake_embed,
        )
    finally:
        _retrieve_mod.COLLECTION_NAME = original_collection  # type: ignore[assignment]

    assert len(results) == 4, (
        f"expected 4 chunks when legislature_period_id=None (no filter); got {len(results)}"
    )


def test_legislature_period_id_alone_rejected_as_non_selective() -> None:
    """legislature_period_id alone must NOT satisfy selectivity.

    A retrieve() call with only legislature_period_id (no source_type, party_id,
    or party_ids_contains) must raise ValueError BEFORE any embed or Qdrant call.

    Verification:
    1. Create a sentinel embed and sentinel client that raise RuntimeError if called.
    2. Call retrieve(query, legislature_period_id=161) — period alone is NOT selective.
    3. Assert ValueError is raised (the selectivity guard must fire BEFORE the sentinels).
    """
    from src.ingestion.retrieve import retrieve

    def _sentinel_embed(query: str) -> list[float]:  # noqa: ARG001
        raise RuntimeError("embed was called before empty-filter rejection!")

    class _SentinelClient:
        def query_points(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            raise RuntimeError("query_points was called before empty-filter rejection!")

    import pytest as _pytest

    with _pytest.raises(ValueError, match="selective"):
        retrieve(
            query="test query",
            legislature_period_id=161,
            _client=_SentinelClient(),  # type: ignore[arg-type]
            _embed_fn=_sentinel_embed,
        )
