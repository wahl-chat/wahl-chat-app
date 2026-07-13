# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Create ``wahlchat_chunks_{env}`` with HNSW m=0/payload_m=16, 3072-dim COSINE
vectors, and all sixteen payload indexes — run BEFORE any upsert.

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

from qdrant_client import QdrantClient, models

# ---------------------------------------------------------------------------
# Guard constants — NEVER change these after the first production run.
# Changing EMBEDDING_DIM invalidates the whole HNSW index; changing
# EMBEDDING_MODEL drifts embeddings and corrupts cosine-similarity scores.
# ---------------------------------------------------------------------------
EMBEDDING_DIM: int = 3072  # text-embedding-3-large output dimension
EMBEDDING_MODEL: str = "text-embedding-3-large"  # OpenAI embedding model

# ---------------------------------------------------------------------------
# Collection name — env-scoped so dev/prod are isolated.
# ---------------------------------------------------------------------------
ENV: str = os.getenv("ENV", "dev")
COLLECTION_NAME: str = f"wahlchat_chunks_{ENV}"

# ---------------------------------------------------------------------------
# Client wiring — mirrors vector_store_helper.py lines 57-60.
# api_key is None in local dev; that is valid for an unauthenticated Qdrant.
# ---------------------------------------------------------------------------
_client = QdrantClient(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

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
# Cursor + pledge payload fields:
# external_id:    integer range index for order_by DESC cursor.
#                 MUST use IntegerIndexParams(range=True) — shorthand PayloadSchemaType.INTEGER
#                 may not enable range support and silently breaks the cursor query.
# status:         keyword (pledge fulfillment status filtering).
# as_of_date:     datetime (pledge recency scoping).
# claim_id:       keyword (cross-party claim lookup).
# Envelope+meta fields:
# wahlperiode:    integer equality index (Wahlperiode number, e.g. 19 for 19th Bundestag).
#                 lookup=True for MatchValue equality; range=False (no range needed).
# legislature_period_id: AW parliament_period ID (globally unique integer, e.g. 161 for
#                 21st Bundestag). Equality-only lookup for retrieve() filter + per-legislature
#                 cursor in discover(). lookup=True, range=False.
#                 NOT indexed: meta.* (nested meta is intentionally un-indexed).
# ---------------------------------------------------------------------------
_INDEX_SPECS: list[tuple[str, models.PayloadSchemaType | models.KeywordIndexParams | models.DatetimeIndexParams | models.UuidIndexParams | models.IntegerIndexParams]] = [
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
    ("party_ids",      models.PayloadSchemaType.KEYWORD),
    ("region",         models.PayloadSchemaType.KEYWORD),
    ("region_path",    models.PayloadSchemaType.KEYWORD),
    ("authority_tier", models.PayloadSchemaType.KEYWORD),
    ("source_type",    models.PayloadSchemaType.KEYWORD),
    (
        "publish_date",
        models.DatetimeIndexParams(type=models.DatetimeIndexType.DATETIME),
    ),
    (
        "source_item_id",
        models.UuidIndexParams(type=models.UuidIndexType.UUID),
    ),
    # Cursor + pledge payload fields:
    (
        "external_id",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,   # support MatchValue equality (dedup checks)
            range=True,    # REQUIRED for order_by DESC cursor query
        ),
    ),
    ("status",    models.PayloadSchemaType.KEYWORD),    # pledge status filtering
    (
        "as_of_date",
        models.DatetimeIndexParams(type=models.DatetimeIndexType.DATETIME),
    ),                                                  # pledge recency scoping
    ("claim_id",  models.PayloadSchemaType.KEYWORD),    # cross-party claim lookup
    (
        "wahlperiode",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,    # support MatchValue equality filter (retrieve() wahlperiode arg)
            range=False,    # no range queries needed for legislative period
        ),
    ),
    (
        "legislature_period_id",
        models.IntegerIndexParams(
            type=models.IntegerIndexType.INTEGER,
            lookup=True,    # support MatchValue equality filter (retrieve() + cursor)
            range=False,    # no range queries needed for period filtering
        ),
    ),
    # Cross-source speech coexist fields (Phase 11):
    # speech_key: deterministic dedup identity — supersede-delete filter (D-04)
    #             + DIP pre-insert resurrection-guard lookup (D-05).
    # source:     "dip"|"op" discriminator — source-scoped cursor in run.py (D-11).
    ("speech_key", models.PayloadSchemaType.KEYWORD),
    ("source",     models.PayloadSchemaType.KEYWORD),
]

_REQUIRED_INDEXES: frozenset[str] = frozenset(field for field, _ in _INDEX_SPECS)


def setup(client: QdrantClient = _client) -> None:
    """Create ``COLLECTION_NAME`` and all sixteen payload indexes.

    Idempotent: safe to call multiple times; existence-guarded before
    ``create_collection``; ``create_payload_index(wait=True)`` is a no-op
    when the same params are re-submitted.

    Args:
        client: QdrantClient instance (default: module-level singleton).

    Raises:
        RuntimeError: if self-verification fails (index missing after
                      creation — should never occur on a healthy Qdrant).
    """
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
    # Create / overwrite all sixteen payload indexes.
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
        raise RuntimeError(
            f"SC1 FAIL: payload indexes missing after creation: {missing!r}"
        )
    print(f"SC1 VERIFIED: all {len(_REQUIRED_INDEXES)} payload indexes present")


if __name__ == "__main__":
    try:
        setup()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
