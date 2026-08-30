# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Create ``wahlchat_chunks_{env}`` with HNSW m=0/payload_m=16, 3072-dim COSINE
vectors, and every payload index in ``_INDEX_SPECS`` — run BEFORE any upsert.

    uv run python -m ingestion.setup_collection

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

# CLI startup ONLY: load ingestion/.env BEFORE the constants below freeze
# their env-derived values. Without this, `python -m ingestion.setup_collection`
# (and `make bootstrap-collection`) resolves the built-in OpenAI defaults even
# when .env configures Gemini — and would stamp/verify the WRONG
# embedding-space fingerprint. Library imports stay side-effect free; exported
# shell env keeps winning (override=False).
if __name__ == "__main__":
    from pathlib import Path

    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parents[2] / ".env"

    # Fall back to ai-backend/.env so setups that keep every key in one
    # file keep working after the ingestion split.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

from qdrant_client import QdrantClient, models

# ---------------------------------------------------------------------------
# The vector space, the collection name, and the fingerprint read/verify helpers
# live in ingestion/corpus.py — duplicated verbatim in the backend, which has to
# agree with them on every query. Only the WRITE side is here, and it is
# re-exported so existing `from ingestion.setup_collection import ...` callers
# (the runner, the connectors, the entrypoint) keep working unchanged.
# ---------------------------------------------------------------------------
from ingestion.corpus import (  # noqa: E402
    COLLECTION_NAME,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    ENV,
    FINGERPRINT_POINT_ID,
    FINGERPRINT_SOURCE_TYPE,
    _make_client,
    check_fingerprint,
    corpus_point_count,
    expected_fingerprint,
    fingerprint_mismatch,
    read_fingerprint,
    resolve_embedding_provider,
)

__all__ = [
    "COLLECTION_NAME",
    "EMBEDDING_DIM",
    "EMBEDDING_MODEL",
    "ENV",
    "FINGERPRINT_POINT_ID",
    "FINGERPRINT_SOURCE_TYPE",
    "check_fingerprint",
    "corpus_point_count",
    "expected_fingerprint",
    "fingerprint_mismatch",
    "read_fingerprint",
    "resolve_embedding_provider",
    "setup",
    "write_fingerprint",
]


def write_fingerprint(client: QdrantClient, collection_name: str) -> None:
    """Upsert the fingerprint point for the current configuration.

    Write side only — the backend verifies fingerprints but never stamps them,
    which is why this stays here rather than in the shared corpus module.
    """
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
        # Pass the name explicitly: this module can be retargeted at another
        # collection (tests swap COLLECTION_NAME here), and corpus.py would
        # otherwise count its own global — i.e. the real corpus.
        populated = corpus_point_count(client, COLLECTION_NAME)
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
