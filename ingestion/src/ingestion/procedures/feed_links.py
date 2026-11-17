# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Feed items ↔ procedures.

A vote item takes its vote chunk's links (tally-checked). A debate item
takes the procedures its Drucksachen belong to, or else the procedure most
of its speeches are linked to. Items carry the ids and a summary of each
procedure, so the web can show where a law stands without another read.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol

from qdrant_client import QdrantClient

from ingestion.ids import compute_chunk_id, compute_source_item_id
from ingestion.procedures.store import ProcedureStore
from wahlchat_common.procedures import PROCEDURES_COLLECTION, ProcedureRecord, ProcedureSummary

if TYPE_CHECKING:
    from ingestion.feed.models import FeedItem

logger = logging.getLogger(__name__)

FEED_ITEMS = "feed_items"
_ANY_LIMIT = 30  # Firestore array-contains-any takes at most 30 values


class ProcedureLookup(Protocol):
    def by_ids(self, ids: Iterable[str]) -> list[ProcedureSummary]: ...

    def ids_for_drucksachen(self, numbers: Iterable[str]) -> list[str]: ...


class FirestoreProcedures:
    """Reads procedures once per id and run."""

    def __init__(self, db: Any) -> None:
        self._db = db
        self._records: dict[str, Optional[ProcedureRecord]] = {}
        self._by_number: dict[str, list[str]] = {}

    def _load(self, ids: Iterable[str]) -> None:
        missing = set(ids) - set(self._records)
        found = ProcedureStore(self._db).get(missing)
        self._records.update({vid: found.get(vid) for vid in missing})

    def by_ids(self, ids: Iterable[str]) -> list[ProcedureSummary]:
        wanted = list(dict.fromkeys(ids))
        self._load(wanted)
        return [r.summary() for vid in wanted if (r := self._records.get(vid)) is not None]

    def ids_for_drucksachen(self, numbers: Iterable[str]) -> list[str]:
        wanted = sorted(set(numbers) - set(self._by_number))
        collection = self._db.collection(PROCEDURES_COLLECTION)
        for start in range(0, len(wanted), _ANY_LIMIT):
            batch = wanted[start : start + _ANY_LIMIT]
            query = collection.where("drucksache_numbers", "array_contains_any", batch)
            found: dict[str, list[str]] = {number: [] for number in batch}
            for snapshot in query.stream():
                record = ProcedureRecord.model_validate(snapshot.to_dict())
                self._records[snapshot.id] = record
                for number in set(record.drucksache_numbers) & set(batch):
                    found[number].append(snapshot.id)
            # Cached only once the query answered; a failure is asked again.
            self._by_number.update(found)
        return sorted({vid for n in numbers for vid in self._by_number.get(n, [])})


def majority_procedures(speech_links: Sequence[Sequence[str]]) -> list[str]:
    """Procedures at least half of the linked speeches point to."""
    linked = [links for links in speech_links if links]
    if not linked:
        return []
    counts = Counter(vid for links in linked for vid in set(links))
    return sorted(vid for vid, n in counts.items() if n * 2 >= len(linked))


def vote_procedure_ids(qdrant: QdrantClient, collection: str, poll_ids: Iterable[int]) -> dict[int, list[str]]:
    """poll id → the vorgang_ids on its vote chunk (one chunk per poll)."""
    ids = {
        str(compute_chunk_id(compute_source_item_id("vote_record", str(pid)), 0)): int(pid)
        for pid in poll_ids
    }
    if not ids:
        return {}
    points = qdrant.retrieve(
        collection_name=collection, ids=list(ids), with_payload=["vorgang_ids"], with_vectors=False
    )
    return {ids[str(p.id)]: list((p.payload or {}).get("vorgang_ids") or []) for p in points}


def procedure_ids_for_item(
    item: dict[str, Any],
    *,
    lookup: ProcedureLookup,
    vote_links: dict[int, list[str]],
    speech_links: Sequence[Sequence[str]] = (),
) -> list[str]:
    """The procedures a stored feed item (as a dict) is about."""
    vote = item.get("vote") or {}
    debate = item.get("debate") or {}
    if vote:
        linked = vote_links.get(int(vote.get("poll_id") or 0))
        if linked:
            return sorted(linked)
        return lookup.ids_for_drucksachen(vote.get("drucksachen") or [])
    from_documents = lookup.ids_for_drucksachen(debate.get("drucksachen") or [])
    return from_documents or majority_procedures(speech_links) or list(item.get("procedure_ids") or [])


def _summaries_json(summaries: list[ProcedureSummary]) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in summaries]


def link_feed_items(
    db: Any,
    qdrant: QdrantClient,
    collection: str,
    *,
    lookup: ProcedureLookup,
    only_ids: Optional[set[str]] = None,
    dry_run: bool = False,
) -> int:
    """Attach (or refresh) procedures on stored Bundestag feed items.

    ``only_ids`` limits the pass to items already pointing at those
    procedures (a procedure got a new stage); None goes over every item.
    """
    items = db.collection(FEED_ITEMS)
    if only_ids is not None:
        snapshots: list[Any] = []
        seen: set[str] = set()
        wanted = sorted(only_ids)
        for start in range(0, len(wanted), _ANY_LIMIT):
            query = items.where("procedure_ids", "array_contains_any", wanted[start : start + _ANY_LIMIT])
            for snapshot in query.stream():
                if snapshot.id not in seen:
                    seen.add(snapshot.id)
                    snapshots.append(snapshot)
    else:
        snapshots = [s for s in items.where("parliament", "==", "bundestag").stream()]
    data = {s.id: s.to_dict() or {} for s in snapshots}
    polls = [int(d["vote"]["poll_id"]) for d in data.values() if (d.get("vote") or {}).get("poll_id")]
    vote_links = vote_procedure_ids(qdrant, collection, polls)
    updated = 0
    writes = db.batch()
    pending = 0
    for doc_id, item in sorted(data.items()):
        ids = procedure_ids_for_item(item, lookup=lookup, vote_links=vote_links)
        summaries = _summaries_json(lookup.by_ids(ids))
        if ids == item.get("procedure_ids") and summaries == item.get("procedures"):
            continue
        updated += 1
        if dry_run:
            continue
        writes.update(items.document(doc_id), {"procedure_ids": ids, "procedures": summaries})
        pending += 1
        if pending == 400:
            writes.commit()
            writes, pending = db.batch(), 0
    if pending and not dry_run:
        writes.commit()
    logger.info("Feed items with new procedure links: %d of %d", updated, len(data))
    return updated


# The feed run's view: an item and its speeches' links → ids + summaries.
ProcedureFacts = Callable[["FeedItem", Sequence[Sequence[str]]], tuple[list[str], list[ProcedureSummary]]]


def procedure_facts(db: Any, qdrant: QdrantClient, collection: str) -> ProcedureFacts:
    lookup = FirestoreProcedures(db)

    def facts(item: "FeedItem", speech_links: Sequence[Sequence[str]]) -> tuple[list[str], list[ProcedureSummary]]:
        try:
            return _facts(item, speech_links)
        except Exception as exc:  # noqa: BLE001 — the item keeps what it had; next run retries
            logger.warning("Procedures for feed item %s: %s", item.id, exc)
            return list(item.procedure_ids), list(item.procedures)

    def _facts(item: "FeedItem", speech_links: Sequence[Sequence[str]]) -> tuple[list[str], list[ProcedureSummary]]:
        vote_links = (
            vote_procedure_ids(qdrant, collection, [item.vote.poll_id]) if item.vote is not None else {}
        )
        ids = procedure_ids_for_item(
            item.model_dump(mode="json"), lookup=lookup, vote_links=vote_links, speech_links=speech_links
        )
        return ids, lookup.by_ids(ids)

    return facts
