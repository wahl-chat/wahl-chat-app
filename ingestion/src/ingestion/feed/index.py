# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Semantic index of feed items: ``wahlchat_feed_{ENV}`` in Qdrant.

Firestore ``feed_items`` holds the items; this collection only finds them.
Its payload is ids and filter fields, never text, so the item has exactly one
source of truth. It is kept apart from the corpus collection on purpose:

- the corpus is tuned for per-party tenancy (HNSW ``m=0``), feed items span
  parties and are searched by region, date and topic;
- the corpus holds primary sources the chat cites. Our own summaries in it
  would let the chat cite them as if they were sources.

Same locked vector space as the corpus (model, dimension, COSINE) and the same
fingerprint guard. One vector per item, embedded from the German text; the
embedding model is multilingual, so queries in other languages match too.
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time. override=False keeps exported
# variables (make, CI, the job spec) in force; Cloud Run has no .env.
if __name__ == "__main__":
    from pathlib import Path as _Path

    from dotenv import load_dotenv

    _env_path = _Path(__file__).resolve().parents[3] / ".env"
    # Use ai-backend/.env when ingestion/.env does not exist.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Optional

from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient, models

from ingestion.feed.items import content_hash
from ingestion.feed.models import CANONICAL_LOCALE, FeedItem
from ingestion.ids import WAHL_CHAT_NS
from ingestion.run import DimensionMismatchError, _embed_texts
from ingestion.setup_collection import (
    EMBEDDING_DIM,
    ENV,
    check_fingerprint,
    read_fingerprint,
    write_fingerprint,
)

FEED_COLLECTION_NAME: str = os.getenv("FEED_COLLECTION_NAME", f"wahlchat_feed_{ENV}")

_INDEX_SPECS: list[tuple[str, Any]] = [
    ("item_id", models.PayloadSchemaType.KEYWORD),
    ("kind", models.PayloadSchemaType.KEYWORD),
    ("parliament", models.PayloadSchemaType.KEYWORD),
    ("region", models.PayloadSchemaType.KEYWORD),
    ("date", models.DatetimeIndexParams(type=models.DatetimeIndexType.DATETIME)),
    ("topics", models.PayloadSchemaType.KEYWORD),
    ("party_ids", models.PayloadSchemaType.KEYWORD),
    ("status", models.PayloadSchemaType.KEYWORD),
]


def setup_feed_collection(
    client: QdrantClient, collection_name: str = FEED_COLLECTION_NAME
) -> None:
    """Create the collection and its indexes; stamp or verify its fingerprint.

    Idempotent. Unlike the corpus there is no adopt path: the collection is
    derived and cheap to rebuild, so an unproven one is simply refused.
    """
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=EMBEDDING_DIM, distance=models.Distance.COSINE
                )
            },
        )
    for field_name, schema in _INDEX_SPECS:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=schema,
            wait=True,
        )
    if read_fingerprint(client, collection_name) is None:
        if client.count(collection_name=collection_name, exact=True).count:
            raise RuntimeError(
                f"collection '{collection_name}' holds points but no "
                "embedding-space fingerprint. Delete it and rebuild the index."
            )
        write_fingerprint(client, collection_name)
    else:
        check_fingerprint(client, collection_name)


def feed_point_id(item_id: str) -> str:
    return str(uuid.uuid5(WAHL_CHAT_NS, f"feed_item:{item_id}"))


def embed_text(item: FeedItem) -> str:
    content = item.content[CANONICAL_LOCALE]
    names = {
        p.party_id: p.party_name for p in (item.debate.parties if item.debate else [])
    }
    lines = [content.headline]
    if content.teaser:
        lines.append(content.teaser)
    lines += content.key_points
    lines += [
        f"{names.get(p.party_id, p.party_id)}: {p.text}" for p in content.positions
    ]
    return "\n".join(lines)


def _day_start(day: date) -> str:
    return datetime.combine(day, time.min, tzinfo=timezone.utc).isoformat()


def item_payload(item: FeedItem) -> dict[str, Any]:
    if item.debate:
        party_ids = [p.party_id for p in item.debate.parties]
    elif item.vote:
        party_ids = [p.party_id for p in item.vote.parties]
    else:
        party_ids = []
    return {
        "item_id": item.id,
        "kind": item.kind,
        "parliament": item.parliament,
        "region": item.region,
        "date": _day_start(item.date),
        "topics": list(item.topics),
        "party_ids": party_ids,
        "status": item.status,
        "content_hash": content_hash(item.content[CANONICAL_LOCALE]),
    }


@dataclass
class IndexReport:
    upserted: int = 0
    unchanged: int = 0
    deleted: int = 0


def _stored_hashes(
    qdrant: QdrantClient, collection_name: str, point_ids: list[str]
) -> dict[str, Optional[str]]:
    points = qdrant.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=["content_hash"],
        with_vectors=False,
    )
    return {str(p.id): (p.payload or {}).get("content_hash") for p in points}


def index_items(
    qdrant: QdrantClient,
    embed: Embeddings,
    items: list[FeedItem],
    collection_name: str = FEED_COLLECTION_NAME,
) -> IndexReport:
    """Upsert published items whose German text changed; drop retracted ones."""
    check_fingerprint(qdrant, collection_name)
    report = IndexReport()

    retracted = [feed_point_id(i.id) for i in items if i.status == "retracted"]
    if retracted:
        qdrant.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(points=retracted),
            wait=True,
        )
        report.deleted = len(retracted)

    published = [i for i in items if i.status == "published"]
    if not published:
        return report
    stored = _stored_hashes(
        qdrant, collection_name, [feed_point_id(i.id) for i in published]
    )
    changed: list[tuple[FeedItem, dict[str, Any]]] = []
    for item in published:
        payload = item_payload(item)
        if stored.get(feed_point_id(item.id)) == payload["content_hash"]:
            # Text unchanged: refresh the filters without paying for a vector.
            qdrant.set_payload(
                collection_name=collection_name,
                payload=payload,
                points=[feed_point_id(item.id)],
                wait=True,
            )
            report.unchanged += 1
        else:
            changed.append((item, payload))
    if not changed:
        return report

    vectors = _embed_texts(embed, [embed_text(item) for item, _ in changed])
    points = []
    for (item, payload), vector in zip(changed, vectors, strict=True):
        if len(vector) != EMBEDDING_DIM:
            raise DimensionMismatchError(
                f"embedding dim mismatch: expected {EMBEDDING_DIM}, "
                f"got {len(vector)} for feed item {item.id!r}"
            )
        points.append(
            models.PointStruct(
                id=feed_point_id(item.id), vector={"dense": vector}, payload=payload
            )
        )
    qdrant.upsert(collection_name=collection_name, points=points, wait=True)
    report.upserted = len(points)
    return report


def search_filter(
    *,
    regions: Optional[list[str]] = None,
    since: Optional[date] = None,
    topics: Optional[list[str]] = None,
    kinds: Optional[list[str]] = None,
) -> models.Filter:
    must: list[models.Condition] = [
        models.FieldCondition(key="status", match=models.MatchValue(value="published"))
    ]
    if regions:
        must.append(
            models.FieldCondition(key="region", match=models.MatchAny(any=regions))
        )
    if topics:
        must.append(
            models.FieldCondition(key="topics", match=models.MatchAny(any=topics))
        )
    if kinds:
        must.append(models.FieldCondition(key="kind", match=models.MatchAny(any=kinds)))
    if since:
        must.append(
            models.FieldCondition(
                key="date", range=models.DatetimeRange(gte=_day_start(since))
            )
        )
    return models.Filter(must=must)


def search_feed(
    qdrant: QdrantClient,
    embed_query: Embeddings,
    query: str,
    *,
    regions: Optional[list[str]] = None,
    since: Optional[date] = None,
    topics: Optional[list[str]] = None,
    kinds: Optional[list[str]] = None,
    limit: int = 10,
    collection_name: str = FEED_COLLECTION_NAME,
) -> list[tuple[str, float]]:
    """Ids of the published items closest to ``query``, with their scores.

    The ids resolve against Firestore ``feed_items``. ``embed_query`` should be
    built with the query task type, the items were embedded as documents.
    """
    check_fingerprint(qdrant, collection_name)
    vector = embed_query.embed_query(query)
    hits = qdrant.query_points(
        collection_name=collection_name,
        query=vector,
        using="dense",
        query_filter=search_filter(
            regions=regions, since=since, topics=topics, kinds=kinds
        ),
        limit=limit,
        with_payload=["item_id"],
    ).points
    return [(str((hit.payload or {})["item_id"]), hit.score) for hit in hits]


if __name__ == "__main__":
    setup_feed_collection(
        QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY") or None,
        )
    )
    print(f"Feed collection '{FEED_COLLECTION_NAME}' ready.")
