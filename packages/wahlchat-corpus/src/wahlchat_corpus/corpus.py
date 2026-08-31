# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Which collection, which embedding space, and the fingerprint proving a reader
and a writer agree about it.

EMBEDDING_* / ENV / COLLECTION_NAME override per deployment. The write side
(index specs, collection creation) is in ingestion's ``setup_collection.py``.
"""

from __future__ import annotations

import os
from typing import Optional

from qdrant_client import QdrantClient, models

# Defaults match the deployed corpus. Immutable for a given collection: changing
# DIM invalidates the HNSW index, changing MODEL corrupts cosine similarity
# against existing vectors.
_DEFAULT_PROVIDER = "gemini"
_DEFAULT_MODEL = "gemini-embedding-2"
_DEFAULT_DIM = 3072

EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", str(_DEFAULT_DIM)))
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", _DEFAULT_MODEL)

# Env-scoped so dev/prod are isolated; COLLECTION_NAME overrides outright.
ENV: str = os.getenv("ENV", "dev")
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", f"wahlchat_chunks_{ENV}")

# A reserved point recording provider+model+dim. Two different 3072-dim spaces
# pass the dimension check while returning garbage, so the name alone is not
# enough. Invisible to retrieval; excluded from corpus_point_count().
FINGERPRINT_POINT_ID: str = "00000000-0000-4000-8000-00000000f19e"
FINGERPRINT_SOURCE_TYPE: str = "corpus_fingerprint"


def resolve_embedding_provider() -> str:
    """Resolve EMBEDDING_PROVIDER the same way the embeddings factory does."""
    return os.getenv("EMBEDDING_PROVIDER", _DEFAULT_PROVIDER).strip().lower()


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

    Raises when a stored fingerprint CONTRADICTS the current config — the main
    runtime guard against the two packages drifting apart. A missing fingerprint
    or an unreachable client degrades to a pass.
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


# Lazy: this module is imported project-wide just for the constants, so a
# module-level client would leak an unused connection into every process.
def _make_client() -> QdrantClient:
    """Construct the default QdrantClient from QDRANT_URL / QDRANT_API_KEY."""
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )


def corpus_point_count(
    client: Optional[QdrantClient] = None,
    collection_name: Optional[str] = None,
) -> Optional[int]:
    """Point count, or None if the collection is absent (rollout gate needs to
    tell missing from empty).

    ``collection_name`` is explicit because callers that retarget the collection
    live in another module now — mutating their own COLLECTION_NAME would not be
    seen here, and the failure mode is silently counting the real corpus.
    """
    c = client or _make_client()
    target = collection_name or COLLECTION_NAME
    if not c.collection_exists(target):
        return None
    # Exclude the fingerprint sentinel: a collection holding ONLY the
    # fingerprint must still read as empty (the rollout gate keys on >0).
    return c.count(
        collection_name=target,
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
