# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Where procedures are written: Firestore records and Qdrant chunks."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
import logging
from typing import Any, Optional

from qdrant_client import QdrantClient, models

from ingestion.ids import compute_chunk_id
from ingestion.run import _embed_texts, _upsert_chunks
from ingestion.schemas import ChunkRecord
from wahlchat_common.procedures import PROCEDURES_COLLECTION, ProcedureRecord, StepSummary

META_COLLECTION = "procedures_meta"
SYNC_DOC = "sync"

_FIRESTORE_BATCH = 400
_GET_BATCH = 100
_SCROLL_PAGE = 512
_EMBED_BATCH = 100

logger = logging.getLogger(__name__)


def _chunks(items: list[Any], size: int) -> Iterator[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class ProcedureStore:
    """Firestore ``procedures`` plus the job's sync state."""

    def __init__(self, db: Any) -> None:
        self._db = db

    def get(self, ids: Iterable[str]) -> dict[str, ProcedureRecord]:
        out: dict[str, ProcedureRecord] = {}
        collection = self._db.collection(PROCEDURES_COLLECTION)
        for batch in _chunks(sorted(set(ids)), _GET_BATCH):
            refs = [collection.document(vid) for vid in batch]
            for snapshot in self._db.get_all(refs):
                if snapshot.exists:
                    out[snapshot.id] = ProcedureRecord.model_validate(snapshot.to_dict())
        return out

    def all(self) -> dict[str, ProcedureRecord]:
        return {
            snapshot.id: ProcedureRecord.model_validate(snapshot.to_dict())
            for snapshot in self._db.collection(PROCEDURES_COLLECTION).stream()
        }

    def put(self, records: Iterable[ProcedureRecord]) -> None:
        collection = self._db.collection(PROCEDURES_COLLECTION)
        for batch in _chunks(list(records), _FIRESTORE_BATCH):
            writes = self._db.batch()
            for record in batch:
                writes.set(collection.document(record.vorgang_id), record.model_dump(mode="json"))
            writes.commit()

    def set_has_links(self, flags: dict[str, bool]) -> None:
        collection = self._db.collection(PROCEDURES_COLLECTION)
        for batch in _chunks(sorted(flags.items()), _FIRESTORE_BATCH):
            writes = self._db.batch()
            for vid, linked in batch:
                writes.update(collection.document(vid), {"has_links": linked})
            writes.commit()

    def set_step_summaries(self, vorgang_id: str, summaries: dict[str, StepSummary]) -> None:
        self._db.collection(PROCEDURES_COLLECTION).document(vorgang_id).update(
            {"step_summaries": {n: s.model_dump(mode="json") for n, s in summaries.items()}}
        )

    def sync_state(self) -> dict[str, Any]:
        snapshot = self._db.collection(META_COLLECTION).document(SYNC_DOC).get()
        return (snapshot.to_dict() or {}) if snapshot.exists else {}

    def set_sync_state(self, state: dict[str, Any]) -> None:
        self._db.collection(META_COLLECTION).document(SYNC_DOC).set(state)


@dataclass
class ChunkWriteReport:
    written: int = 0
    skipped: int = 0
    deleted: int = 0
    failed_parents: list[str] = field(default_factory=list)


def _point_id(chunk: ChunkRecord) -> str:
    return str(compute_chunk_id(chunk.source_item_id, chunk.chunk_index))


def stored_parent_points(
    qdrant: QdrantClient, collection: str, parent_keys: Iterable[str]
) -> dict[str, dict[str, Optional[str]]]:
    """parent key → {point id: content_hash} for everything stored under it."""
    keys = sorted(set(parent_keys))
    out: dict[str, dict[str, Optional[str]]] = {k: {} for k in keys}
    for batch in _chunks(keys, 64):
        offset = None
        while True:
            points, offset = qdrant.scroll(
                collection_name=collection,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_parent_key", match=models.MatchAny(any=batch)
                        )
                    ]
                ),
                limit=_SCROLL_PAGE,
                offset=offset,
                with_payload=["source_parent_key", "content_hash"],
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                out[payload["source_parent_key"]][str(point.id)] = payload.get("content_hash")
            if offset is None:
                break
    return out


def _groups(keys: list[str], parents: dict[str, list[ChunkRecord]]) -> Iterator[list[str]]:
    """Parents grouped to about one embedding batch of chunks each."""
    group: list[str] = []
    size = 0
    for key in keys:
        if group and size + len(parents[key]) > _EMBED_BATCH:
            yield group
            group, size = [], 0
        group.append(key)
        size += len(parents[key])
    if group:
        yield group


def replace_parents(
    qdrant: QdrantClient,
    collection: str,
    embed: Any,
    parents: dict[str, list[ChunkRecord]],
) -> ChunkWriteReport:
    """Make each parent's stored chunks exactly ``parents[key]``.

    Unchanged parents (same point ids, same hashes) are skipped. Changed
    parents are embedded in shared batches, then each is upserted first and
    only afterwards loses the points it no longer emits, by exact id. A parent
    whose embedding or upsert fails keeps its old points and is reported.
    """
    report = ChunkWriteReport()
    stored = stored_parent_points(qdrant, collection, parents)
    changed: list[str] = []
    for key, chunks in parents.items():
        if {_point_id(c): c.content_hash for c in chunks} == stored[key]:
            report.skipped += 1
        else:
            changed.append(key)

    for keys in _groups(changed, parents):
        texts = [c.text for key in keys for c in parents[key]]
        try:
            vectors = [
                vector
                for batch in _chunks(texts, _EMBED_BATCH)
                for vector in _embed_texts(embed, batch)
            ]
        except Exception:  # noqa: BLE001 — these parents are retried next run
            logger.exception("Embedding failed for %d parents", len(keys))
            report.failed_parents.extend(keys)
            continue
        position = 0
        for key in keys:
            chunks = parents[key]
            mine = vectors[position : position + len(chunks)]
            position += len(chunks)
            try:
                if chunks:
                    _upsert_chunks(qdrant, collection, chunks, mine)
                wanted = {_point_id(c) for c in chunks}
                orphans = [pid for pid in stored[key] if pid not in wanted]
                if orphans:
                    qdrant.delete(
                        collection_name=collection,
                        points_selector=models.PointIdsList(points=orphans),
                        wait=True,
                    )
            except Exception:  # noqa: BLE001 — the parent is retried next run
                logger.exception("Writing %s failed", key)
                report.failed_parents.append(key)
                continue
            report.written += 1
            report.deleted += len(orphans)
    return report
