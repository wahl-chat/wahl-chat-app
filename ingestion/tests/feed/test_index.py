# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date
from types import SimpleNamespace
from typing import Any

from ingestion.feed.index import (
    embed_text,
    feed_point_id,
    index_items,
    item_payload,
    search_filter,
)
from ingestion.feed.models import FeedItem
from ingestion.setup_collection import EMBEDDING_DIM
from tests.feed.samples import sample_items


def _items() -> list[FeedItem]:
    return sample_items()


class FakeEmbeddings:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.texts.extend(texts)
        return [[0.1] * EMBEDDING_DIM for _ in texts]


class FakeQdrant:
    def __init__(self) -> None:
        self.points: dict[str, dict[str, Any]] = {}
        self.deleted: list[str] = []

    def retrieve(self, collection_name: str, ids: list[str], **_: Any) -> list:
        return [
            SimpleNamespace(id=i, payload=self.points[i])
            for i in ids
            if i in self.points
        ]

    def upsert(self, collection_name: str, points: list, **_: Any) -> None:
        for point in points:
            self.points[str(point.id)] = point.payload

    def set_payload(
        self, collection_name: str, payload: dict, points: list[str], **_: Any
    ) -> None:
        for point_id in points:
            self.points[point_id] = payload

    def delete(self, collection_name: str, points_selector: Any, **_: Any) -> None:
        self.deleted.extend(points_selector.points)
        for point_id in points_selector.points:
            self.points.pop(point_id, None)


def test_payload_carries_ids_and_filters_but_no_text() -> None:
    item = _items()[0]
    payload = item_payload(item)
    assert payload["item_id"] == item.id
    assert payload["region"] == "DE"
    assert payload["date"].startswith(item.date.isoformat())
    assert payload["status"] == "published"
    assert item.debate is not None
    assert payload["party_ids"] == [p.party_id for p in item.debate.parties]
    flat = json.dumps(payload, ensure_ascii=False)
    assert item.content["de"].headline not in flat


def test_embedded_text_is_the_german_content_with_party_names() -> None:
    item = _items()[0]
    text = embed_text(item)
    assert text.startswith(item.content["de"].headline)
    assert item.debate is not None and item.debate.parties
    assert f"{item.debate.parties[0].party_name}: " in text


def test_only_changed_texts_are_embedded_again() -> None:
    items = _items()
    qdrant, embed = FakeQdrant(), FakeEmbeddings()
    first = index_items(qdrant, embed, items)  # type: ignore[arg-type]
    assert first.upserted == len(items)

    embed.texts.clear()
    items[0].content["de"].headline = "Neu formuliert"
    second = index_items(qdrant, embed, items)  # type: ignore[arg-type]
    assert second.upserted == 1
    assert second.unchanged == len(items) - 1
    assert embed.texts == [embed_text(items[0])]


def test_retracted_items_leave_the_index() -> None:
    items = _items()
    qdrant = FakeQdrant()
    index_items(qdrant, FakeEmbeddings(), items)  # type: ignore[arg-type]
    gone = items[0].model_copy(update={"status": "retracted"})
    report = index_items(qdrant, FakeEmbeddings(), [gone])  # type: ignore[arg-type]
    assert report.deleted == 1
    assert feed_point_id(gone.id) not in qdrant.points


def test_search_only_ever_returns_published_items() -> None:
    conditions = search_filter(
        regions=["DE-ST"], since=date(2026, 7, 1), topics=["health_care"]
    ).must
    assert conditions is not None
    keys = [c.key for c in conditions]  # type: ignore[union-attr]
    assert keys == ["status", "region", "topics", "date"]
    assert conditions[0].match.value == "published"  # type: ignore[union-attr]
