# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from types import SimpleNamespace
from typing import Any

from ingestion.feed.models import FeedItem, LocalizedContent
from ingestion.feed.prompts import TRANSLATION_PROMPT_VERSION
from ingestion.feed.store import (
    carry_over_translations,
    read_edition_item_ids,
    read_items,
    vanished_item_ids,
    write_feed,
)
from tests.feed.samples import sample_items


def _with_english(item: FeedItem) -> FeedItem:
    de = item.content["de"]
    item.content["en"] = LocalizedContent(
        headline="EN",
        origin="translated",
        source_hash=de.source_hash,
        prompt_version=TRANSLATION_PROMPT_VERSION,
        generated_at=de.generated_at,
    )
    return item


class FakeDoc:
    def __init__(self, store: dict, doc_id: str) -> None:
        self.store, self.id = store, doc_id


class FakeDb:
    def __init__(self, docs: dict[str, dict]) -> None:
        self.docs = docs
        self.updates: list[tuple[str, dict]] = []
        self.sets: list[str] = []

    def collection(self, _name: str) -> Any:
        return SimpleNamespace(document=lambda doc_id: FakeDoc(self.docs, doc_id))

    def get_all(self, refs: list[FakeDoc]) -> list[Any]:
        return [
            SimpleNamespace(
                id=r.id,
                exists=r.id in self.docs,
                to_dict=lambda r=r: self.docs[r.id],
            )
            for r in refs
        ]

    def batch(self) -> Any:
        db = self
        return SimpleNamespace(
            update=lambda ref, data: db.updates.append((ref.id, data)),
            set=lambda ref, data: db.sets.append(ref.id),
            commit=lambda: None,
        )


def test_an_item_whose_unit_vanished_is_retracted() -> None:
    assert vanished_item_ids(["a", "b", "c"], ["c", "a"]) == ["b"]


def test_retraction_touches_only_the_status() -> None:
    db = FakeDb({})
    write_feed(db, [], [], ["old"])
    assert db.updates == [("old", {"status": "retracted"})]


def test_a_doc_in_an_older_shape_is_read_as_not_built() -> None:
    [item, *_] = sample_items()
    db = FakeDb(
        {
            item.id: item.model_dump(mode="json"),
            "old": {"id": "old", "legacy_keys": ["x~s0"]},
            "edition": {"item_ids": ["old"], "other_topics": []},
        }
    )
    assert list(read_items(db, [item.id, "old"])) == [item.id]
    assert read_edition_item_ids(db, ["edition", "missing"]) == {"edition": ["old"]}


def test_unchanged_texts_keep_their_translation_across_a_rebuild() -> None:
    stored = {i.id: _with_english(i) for i in sample_items()}
    items = sample_items()
    items[0].content["de"].source_hash = "regenerated differently"

    kept = carry_over_translations(items, stored)
    assert kept == len(items) - 1
    assert "en" not in items[0].content
    assert all("en" in i.content for i in items[1:])
