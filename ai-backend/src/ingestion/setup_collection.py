# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Create ``wahlchat_chunks_{env}`` with HNSW m=0/payload_m=16, 3072-dim COSINE
vectors, and every payload index in ``_INDEX_SPECS`` — run BEFORE any upsert.

    uv run python -m src.ingestion.setup_collection

Re-running is idempotent: if the collection already exists, creation is
skipped; index creation calls are always repeated (Qdrant overwrites
identically-named indexes in-place, which is a no-op for the same params).

On success, prints a verification line and exits with code 0. Raises
RuntimeError if any index is missing (should never happen after a
successful first run).

EMBEDDING_DIM and EMBEDDING_MODEL are the canonical source of truth
for the vector space; changing either would break index parity.

This script NEVER touches the legacy V1 collections
(``all_parties_*``, ``justified_voting_behavior_*``, etc.).
"""

import os
import sys
from typing import Optional

# CLI startup ONLY: load ai-backend/.env BEFORE the constants below freeze
# their env-derived values. Without this, `python -m src.ingestion.setup_collection`
# (and `make bootstrap-collection`) resolves the built-in OpenAI defaults even
# when .env configures Gemini — and would stamp/verify the WRONG
# embedding-space fingerprint. Library imports stay side-effect free; exported
# shell env keeps winning (override=False).
if __name__ == "__main__":
    from pathlib import Path

    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[2] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from qdrant_client import QdrantClient, models

# ---------------------------------------------------------------------------
# Vector-space definition — the canonical source of truth for the corpus index.
# For a GIVEN collection these are immutable after its first run: changing
# EMBEDDING_DIM invalidates the whole HNSW index; changing EMBEDDING_MODEL drifts
# embeddings and corrupts cosine-similarity scores.
#
# They are env-overridable so a SECOND collection with a different vector space
# (e.g. a Gemini collection: EMBEDDING_PROVIDER=gemini, a Gemini EMBEDDING_MODEL,
# a COLLECTION_NAME like wahlchat_chunks_gemini_dev) can be created ALONGSIDE the
# existing one without editing code. With no env set the defaults are exactly the
# locked OpenAI text-embedding-3-large @ 3072 space — unchanged behaviour.
# ---------------------------------------------------------------------------
EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "3072"))
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# ---------------------------------------------------------------------------
# Collection name — env-scoped so dev/prod are isolated; COLLECTION_NAME may be
# overridden outright (e.g. for a parallel Gemini collection).
# ---------------------------------------------------------------------------
ENV: str = os.getenv("ENV", "dev")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", f"wahlchat_chunks_{ENV}")

# ---------------------------------------------------------------------------
# Embedding-space fingerprint — guards against silently mixing vector spaces.
#
# A collection name alone cannot prove which provider/model produced its
# vectors: an OpenAI collection and a Gemini collection can both be 3072-dim,
# so the per-vector dimension guard passes while cosine scores are garbage.
# The fingerprint is a single reserved point (fixed UUID, source_type
# "corpus_fingerprint") whose payload records provider + model + dim. It is
# invisible to retrieval (every query filters on real source_type / party
# fields) and excluded from corpus_point_count().
# ---------------------------------------------------------------------------
FINGERPRINT_POINT_ID: str = "00000000-0000-4000-8000-00000000f19e"
FINGERPRINT_SOURCE_TYPE: str = "corpus_fingerprint"


def resolve_embedding_provider() -> str:
    """Resolve EMBEDDING_PROVIDER the same way the embeddings factory does."""
    return os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()


def expected_fingerprint() -> dict:
    """The fingerprint payload the current configuration should produce."""
    return {
        "source_type": FINGERPRINT_SOURCE_TYPE,
        "embedding_provider": resolve_embedding_provider(),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dim": EMBEDDING_DIM,
    }


def read_fingerprint(client: QdrantClient, collection_name: str) -> Optional[dict]:
    """Return the stored fingerprint payload, or None when absent."""
    points = client.retrieve(
        collection_name=collection_name,
        ids=[FINGERPRINT_POINT_ID],
        with_payload=True,
        with_vectors=False,
    )
    if not points:
        return None
    return points[0].payload


def write_fingerprint(client: QdrantClient, collection_name: str) -> None:
    """Upsert the fingerprint point for the current configuration."""
    # Non-zero unit-ish vector: some engines reject all-zero vectors under
    # COSINE. The vector itself is never searched (no query matches this
    # source_type), only the payload matters.
    vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    client.upsert(
        collection_name=collection_name,
        points=[
            models.PointStruct(
                id=FINGERPRINT_POINT_ID,
                vector={"dense": vector},
                payload=expected_fingerprint(),
            )
        ],
        wait=True,
    )


def fingerprint_mismatch(stored: dict) -> Optional[str]:
    """Compare a stored fingerprint to the current config; describe a mismatch.

    Returns None when they agree, else a human-readable description.
    """
    expected = expected_fingerprint()
    diffs = [
        f"{key}: stored={stored.get(key)!r} configured={expected[key]!r}"
        for key in ("embedding_provider", "embedding_model", "embedding_dim")
        if stored.get(key) != expected[key]
    ]
    if not diffs:
        return None
    return "; ".join(diffs)


def check_fingerprint(client: QdrantClient, collection_name: str) -> None:
    """Best-effort fingerprint verification before writes/queries.

    Raises RuntimeError when a stored fingerprint CONTRADICTS the current
    configuration — that is the silent-vector-space-mix hazard. A missing
    fingerprint (pre-fingerprint store) or an unreachable/limited client
    (test fakes) only degrades to a pass: enforcement starts once setup()
    has stamped the collection.
    """
    try:
        stored = read_fingerprint(client, collection_name)
    except Exception:  # noqa: BLE001 — fakes/legacy stores: nothing to verify
        return
    # Only a well-formed fingerprint payload counts — anything else (None,
    # test doubles returning stand-in objects) means "nothing to verify".
    if (
        not isinstance(stored, dict)
        or stored.get("source_type") != FINGERPRINT_SOURCE_TYPE
    ):
        return
    mismatch = fingerprint_mismatch(stored)
    if mismatch:
        raise RuntimeError(
            f"embedding-space fingerprint mismatch for collection "
            f"'{collection_name}': {mismatch}. Refusing to proceed — mixing "
            "vector spaces corrupts retrieval. Point the configuration at the "
            "collection's original provider/model, or re-ingest into a fresh "
            "collection (COLLECTION_NAME override) and cut over."
        )


# ---------------------------------------------------------------------------
# Client wiring — mirrors vector_store_helper.py lines 57-60, but LAZY:
# this module is imported project-wide just for COLLECTION_NAME /
# EMBEDDING_MODEL, so a module-level QdrantClient would allocate an unused,
# never-closed client in every importing process. The client is constructed
# only inside setup() (when none is injected) / the __main__ path.
# api_key is None in local dev; that is valid for an unauthenticated Qdrant.
# ---------------------------------------------------------------------------
def _make_client() -> QdrantClient:
    """Construct the default QdrantClient from QDRANT_URL / QDRANT_API_KEY."""
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )


def corpus_point_count(client: Optional[QdrantClient] = None) -> Optional[int]:
    """Return the number of points in ``COLLECTION_NAME``, or None if it is absent.

    Used by the app's rollout gate to distinguish a missing collection (None)
    from an empty one (0) from a populated one (>0). Constructs its own client
    when none is injected (tests inject a fake).
    """
    c = client or _make_client()
    if not c.collection_exists(COLLECTION_NAME):
        return None
    # Exclude the fingerprint sentinel: a collection holding ONLY the
    # fingerprint must still read as empty (the rollout gate keys on >0).
    return c.count(
        collection_name=COLLECTION_NAME,
        count_filter=models.Filter(
            must_not=[
                models.FieldCondition(
                    key="source_type",
                    match=models.MatchValue(value=FINGERPRINT_SOURCE_TYPE),
                )
            ]
        ),
        exact=True,
    ).count


# ---------------------------------------------------------------------------
# Index specification list — ORDER MATTERS for readability; Qdrant accepts
# repeated create_payload_index calls for the same field (idempotent).
#
# party_id:       is_tenant=True → per-party HNSW sub-graph (Qdrant 1.16+
#                 tiered multitenancy); all queries add a must filter
#                 on party_id so the global HNSW (m=0) is never used.
# region:         scalar keyword (matches election_region_path via MatchAny).
# region_path:    keyword index kept here for completeness + potential
#                 future source_item-level filtering (chunks store scalar
#                 region, not this array field, but the index itself is
#                 harmless).
# authority_tier: keyword (authoritative | factual_record | …).
# source_type:    keyword (party_manifesto | vote_record | …).
# publish_date:   datetime (context-window scoping at query time).
# source_item_id: uuid (per-source lookup and dedup checks).
# Cursor field:
# external_id:    integer range index for order_by DESC cursor.
#                 MUST use IntegerIndexParams(range=True) — shorthand PayloadSchemaType.INTEGER
#                 may not enable range support and silently breaks the cursor query.
# Envelope+meta fields:
# wahlperiode:    integer equality index (Wahlperiode number, e.g. 19 for 19th Bundestag).
#                 lookup=True for MatchValue equality; range=False (no range needed).
# legislature_period_id: AW parliament_period ID (globally unique integer, e.g. 161 for
#                 21st Bundestag). Equality-only lookup for retrieve() filter + per-legislature
#                 cursor in discover(). lookup=True, range=False.
#                 NOT indexed: meta.* (nested meta is intentionally un-indexed).
# ---------------------------------------------------------------------------
_INDEX_SPECS: list[
    tuple[
        str,
        models.PayloadSchemaType
        | models.KeywordIndexParams
        | models.DatetimeIndexParams
        | models.UuidIndexParams
        | models.IntegerIndexParams,
    ]
] = [
    (
        "party_id",
        models.KeywordIndexParams(
            type=models.KeywordIndexType.KEYWORD,
            is_tenant=True,
        ),
    ),
    # party_ids: participating parties on a vote_record chunk. Plain keyword
    # array index (NOT is_tenant) — a single MatchValue against the array tests
    # membership ("did party X vote on this motion"). A vote belongs to no single
    # party, so it does NOT use the is_tenant party_id key.
    ("party_ids", models.PayloadSchemaType.KEYWORD),
    ("region", models.PayloadSchemaType.KEYWORD),
    ("region_path", models.PayloadSchemaType.KEYWORD),
    ("authority_tier", models.PayloadSchemaType.KEYWORD),
    ("source_type", models.PayloadSchemaType.KEYWORD),
    (
        "publish_date",
        models.DatetimeIndexParams(type=models.DatetimeIndexType.DATETIME),
    ),
    (
        "source_item_id",
        models.UuidIndexParams(type=models.UuidIndexType.UUID),
    ),
    # Cursor field:
    (
        "external_id",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,  # support MatchValue equality (dedup checks)
            range=True,  # REQUIRED for order_by DESC cursor query
        ),
    ),
    (
        "wahlperiode",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,  # support MatchValue equality filter (retrieve() wahlperiode arg)
            range=False,  # no range queries needed for legislative period
        ),
    ),
    (
        "legislature_period_id",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,  # support MatchValue equality filter (retrieve() + cursor)
            range=False,  # no range queries needed for period filtering
        ),
    ),
    # Cross-source speech coexist fields:
    # speech_key: deterministic dedup identity — supersede-delete filter
    #             + DIP pre-insert resurrection-guard lookup.
    # source:     "dip"|"op" discriminator — source-scoped cursor in run.py.
    ("speech_key", models.PayloadSchemaType.KEYWORD),
    ("source", models.PayloadSchemaType.KEYWORD),
    # source_parent_key: stable per-parent identity — run.py scrolls the full
    # parent footprint by it so a wholly-disappeared child is reconciled.
    ("source_parent_key", models.PayloadSchemaType.KEYWORD),
]

_REQUIRED_INDEXES: frozenset[str] = frozenset(field for field, _ in _INDEX_SPECS)


def setup(client: Optional[QdrantClient] = None) -> None:
    """Create ``COLLECTION_NAME`` and every payload index in ``_INDEX_SPECS``.

    Idempotent: safe to call multiple times; existence-guarded before
    ``create_collection``; ``create_payload_index(wait=True)`` is a no-op
    when the same params are re-submitted.

    Args:
        client: QdrantClient instance. When None (the __main__ path), a
                client is constructed lazily from QDRANT_URL/QDRANT_API_KEY —
                importing this module allocates nothing.

    Raises:
        RuntimeError: if self-verification fails (index missing after
                      creation — should never occur on a healthy Qdrant).
    """
    if client is None:
        client = _make_client()
    # -----------------------------------------------------------------------
    # Existence guard — mirrors vector_store_helper.py lines 148-155.
    # -----------------------------------------------------------------------
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME in existing:
        print(f"Collection '{COLLECTION_NAME}' already exists — skipping creation.")
    else:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(
                    size=EMBEDDING_DIM,
                    distance=models.Distance.COSINE,
                )
            },
            hnsw_config=models.HnswConfigDiff(m=0, payload_m=16),
        )
        print(f"Created collection '{COLLECTION_NAME}'.")

    # -----------------------------------------------------------------------
    # Create / overwrite every payload index in _INDEX_SPECS.
    # -----------------------------------------------------------------------
    for field_name, field_schema in _INDEX_SPECS:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=field_schema,
            wait=True,
        )
        print(f"  Index ready: {field_name}")

    # -----------------------------------------------------------------------
    # Self-verification — raise if any required index is absent.
    # -----------------------------------------------------------------------
    info = client.get_collection(COLLECTION_NAME)
    indexed = set(info.payload_schema.keys())
    missing = _REQUIRED_INDEXES - indexed
    if missing:
        raise RuntimeError(f"payload indexes missing after creation: {missing!r}")
    print(f"Collection verified: all {len(_REQUIRED_INDEXES)} payload indexes present")

    # -----------------------------------------------------------------------
    # Embedding-space fingerprint — stamp or verify.
    #   stored + matching      → verified, nothing to do.
    #   stored + mismatch      → RuntimeError (the OpenAI↔Gemini mix hazard).
    #   absent + empty corpus  → stamp with the current configuration.
    #   absent + populated     → refuse by default: the store's vector space is
    #                            unproven. An operator who KNOWS the store
    #                            matches the current configuration adopts it
    #                            explicitly with CORPUS_FINGERPRINT_ADOPT=1.
    # -----------------------------------------------------------------------
    stored = read_fingerprint(client, COLLECTION_NAME)
    if stored is not None:
        mismatch = fingerprint_mismatch(stored)
        if mismatch:
            raise RuntimeError(
                f"embedding-space fingerprint mismatch for collection "
                f"'{COLLECTION_NAME}': {mismatch}. Refusing setup — mixing "
                "vector spaces corrupts retrieval. Point the configuration at "
                "the collection's original provider/model, or create a fresh "
                "collection (COLLECTION_NAME override) and re-ingest."
            )
        print("Embedding-space fingerprint verified.")
    else:
        populated = corpus_point_count(client)
        if populated and os.getenv("CORPUS_FINGERPRINT_ADOPT") != "1":
            raise RuntimeError(
                f"collection '{COLLECTION_NAME}' holds {populated} points but "
                "no embedding-space fingerprint. Refusing to stamp it with the "
                "current configuration blindly. If the store was ingested with "
                "exactly this provider/model/dim, re-run with "
                "CORPUS_FINGERPRINT_ADOPT=1 to adopt it."
            )
        write_fingerprint(client, COLLECTION_NAME)
        print(
            "Embedding-space fingerprint stamped: "
            f"{resolve_embedding_provider()} / {EMBEDDING_MODEL} @ {EMBEDDING_DIM}"
        )


if __name__ == "__main__":
    try:
        setup()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
