# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firestore ``feed_editions/{edition_id}`` and ``feed_items/{item_id}``.

Items are never deleted: one that vanishes from a rebuilt day is marked
``retracted``, so a shared link to it still resolves to something the web can
explain instead of a dead end.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

from google.cloud.firestore_v1.base_query import FieldFilter

from src.feed.models import (
    CANONICAL_LOCALE,
    TRANSLATED_LOCALES,
    FeedEdition,
    FeedItem,
)

EDITION_COLLECTION = "feed_editions"
ITEM_COLLECTION = "feed_items"
# Firestore caps a write batch at 500 operations.
_BATCH_OPS = 450


def read_edition_hashes(db: Any, parliament_ids: list[str]) -> dict[str, Any]:
    """``input_hash`` per stored edition, so unchanged days are skipped."""
    hashes: dict[str, Any] = {}
    for parliament_id in parliament_ids:
        query = db.collection(EDITION_COLLECTION).where(
            filter=FieldFilter("parliament", "==", parliament_id)
        )
        for snapshot in query.stream():
            hashes[snapshot.id] = (snapshot.to_dict() or {}).get("input_hash")
    return hashes


def read_editions(db: Any, edition_ids: Iterable[str]) -> dict[str, FeedEdition]:
    refs = [db.collection(EDITION_COLLECTION).document(i) for i in edition_ids]
    return {
        s.id: FeedEdition.model_validate(s.to_dict())
        for s in (db.get_all(refs) if refs else [])
        if s.exists
    }


def read_items(db: Any, item_ids: Iterable[str]) -> dict[str, FeedItem]:
    refs = [db.collection(ITEM_COLLECTION).document(i) for i in item_ids]
    return {
        s.id: FeedItem.model_validate(s.to_dict())
        for s in (db.get_all(refs) if refs else [])
        if s.exists
    }


def read_items_since(db: Any, parliament_id: str, since: date) -> list[FeedItem]:
    query = (
        db.collection(ITEM_COLLECTION)
        .where(filter=FieldFilter("parliament", "==", parliament_id))
        .where(filter=FieldFilter("date", ">=", since.isoformat()))
        # Descending, so the query is served by the (parliament, date DESC)
        # index the web's feed read needs anyway.
        .order_by("date", direction="DESCENDING")
    )
    return [FeedItem.model_validate(s.to_dict()) for s in query.stream()]


def carry_over_translations(
    items: list[FeedItem], previous: dict[str, FeedItem]
) -> int:
    """Keep stored translations whose German source is unchanged.

    A rebuilt day regenerates every text, but whatever comes out identical
    (a vote nobody touched) need not be translated again.
    """
    kept = 0
    for item in items:
        old = previous.get(item.id)
        if old is None:
            continue
        source_hash = item.content[CANONICAL_LOCALE].source_hash
        for locale in TRANSLATED_LOCALES:
            translation = old.content.get(locale)
            if translation and translation.source_hash == source_hash:
                item.content[locale] = translation
                kept += 1
    return kept


def vanished_items(
    previous: dict[str, FeedEdition],
    editions: list[FeedEdition],
    stored: dict[str, FeedItem],
) -> list[FeedItem]:
    """Stored items a rebuilt edition no longer lists, marked retracted."""
    retracted: list[FeedItem] = []
    for edition in editions:
        old = previous.get(edition.id)
        if old is None:
            continue
        for item_id in set(old.item_ids) - set(edition.item_ids):
            item = stored.get(item_id)
            if item is not None and item.status != "retracted":
                retracted.append(item.model_copy(update={"status": "retracted"}))
    return retracted


def _commit(db: Any, writes: list[tuple[Any, dict]]) -> None:
    for start in range(0, len(writes), _BATCH_OPS):
        batch = db.batch()
        for ref, data in writes[start : start + _BATCH_OPS]:
            batch.set(ref, data)
        batch.commit()


def write_feed(db: Any, editions: list[FeedEdition], items: list[FeedItem]) -> None:
    """Items first, then their editions: an edition never lists an item that
    is not there yet."""
    _commit(
        db,
        [
            (
                db.collection(ITEM_COLLECTION).document(item.id),
                item.model_dump(mode="json"),
            )
            for item in items
        ],
    )
    _commit(
        db,
        [
            (
                db.collection(EDITION_COLLECTION).document(edition.id),
                edition.model_dump(mode="json"),
            )
            for edition in editions
        ],
    )
