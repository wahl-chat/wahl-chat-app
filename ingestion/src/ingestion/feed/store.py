# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firestore ``feed_editions/{edition_id}`` and ``feed_items/{item_id}``.

Items are never deleted: one whose source unit vanishes from a day is marked
``retracted``, so a shared link to it still resolves to something the web can
explain instead of a dead end. Retraction touches only ``status``, so it also
works on a doc stored in an older shape that no longer validates.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Iterable

from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import ValidationError

from ingestion.feed.models import (
    CANONICAL_LOCALE,
    TRANSLATED_LOCALES,
    FeedEdition,
    FeedItem,
)

logger = logging.getLogger(__name__)

EDITION_COLLECTION = "feed_editions"
ITEM_COLLECTION = "feed_items"
# Firestore caps a write batch at 500 operations.
_BATCH_OPS = 450


def _valid_item(snapshot: Any) -> FeedItem | None:
    """The stored item, or None for a doc in an older shape: the caller then
    treats it as not built, which rebuilds it in the current one."""
    try:
        return FeedItem.model_validate(snapshot.to_dict())
    except ValidationError:
        logger.info("Stored item %s has an older shape; rebuilding it", snapshot.id)
        return None


def read_edition_item_ids(db: Any, edition_ids: Iterable[str]) -> dict[str, list[str]]:
    """The item ids each stored edition lists. Read raw, so an edition stored
    in an older shape still says which items to retract."""
    refs = [db.collection(EDITION_COLLECTION).document(i) for i in edition_ids]
    return {
        s.id: list((s.to_dict() or {}).get("item_ids") or [])
        for s in (db.get_all(refs) if refs else [])
        if s.exists
    }


def read_items(db: Any, item_ids: Iterable[str]) -> dict[str, FeedItem]:
    refs = [db.collection(ITEM_COLLECTION).document(i) for i in item_ids]
    found: dict[str, FeedItem] = {}
    for snapshot in db.get_all(refs) if refs else []:
        if snapshot.exists and (item := _valid_item(snapshot)) is not None:
            found[snapshot.id] = item
    return found


def read_items_since(db: Any, parliament_id: str, since: date) -> list[FeedItem]:
    query = (
        db.collection(ITEM_COLLECTION)
        .where(filter=FieldFilter("parliament", "==", parliament_id))
        .where(filter=FieldFilter("date", ">=", since.isoformat()))
        # Descending, so the query is served by the (parliament, date DESC)
        # index the web's feed read needs anyway.
        .order_by("date", direction="DESCENDING")
    )
    return [item for s in query.stream() if (item := _valid_item(s)) is not None]


def carry_over_translations(
    items: list[FeedItem], previous: dict[str, FeedItem]
) -> int:
    """Keep stored translations whose German source is unchanged.

    A rebuilt item regenerates its text, but one that comes out identical (a
    vote whose enrichment fell back to its title again) need not be
    translated again.
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


def vanished_item_ids(previous_ids: list[str], current_ids: list[str]) -> list[str]:
    """Items a stored edition listed whose source unit the day no longer has."""
    current = set(current_ids)
    return [item_id for item_id in previous_ids if item_id not in current]


def _commit(db: Any, writes: list[tuple[Any, dict]]) -> None:
    for start in range(0, len(writes), _BATCH_OPS):
        batch = db.batch()
        for ref, data in writes[start : start + _BATCH_OPS]:
            batch.set(ref, data)
        batch.commit()


def write_feed(
    db: Any,
    editions: list[FeedEdition],
    items: list[FeedItem],
    retracted_ids: Iterable[str] = (),
) -> None:
    """Items first, then their editions: an edition never lists an item that
    is not there yet. Retracted items get their status only."""
    retract = list(retracted_ids)
    for start in range(0, len(retract), _BATCH_OPS):
        batch = db.batch()
        for item_id in retract[start : start + _BATCH_OPS]:
            batch.update(
                db.collection(ITEM_COLLECTION).document(item_id),
                {"status": "retracted"},
            )
        batch.commit()
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
