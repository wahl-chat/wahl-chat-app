# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Read Bundestag procedures (DIP Vorgänge) and what points to them.

Firestore ``procedures/{vorgang_id}`` is the record; Qdrant chunks of votes,
speeches and Drucksachen carry the id in ``vorgang_ids``. Consumers (the
generic chat's ``get_process`` tool, the feed) call these functions; an
unknown id gives None or an empty list, never an error.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any, Optional

from qdrant_client.models import (
    Direction,
    FieldCondition,
    Filter,
    MatchValue,
    OrderBy,
    PayloadSelectorExclude,
)

from src.models.procedures import (
    ProcedureRecord,
    ProcedureSummary,
    ProcedureView,
)
from src.retrieve import COLLECTION_NAME, _get_qdrant, retrieve
from wahlchat_common.procedures import PROCEDURES_COLLECTION, ProcedureKind
from wahlchat_common.speech_dedup import dedup_prefer_op

logger = logging.getLogger(__name__)

# Speech payloads carry a sentence-by-sentence video map; a view needs none of it.
_VIEW_PAYLOAD_EXCLUDE = ["meta.sentence_map"]


def _default_db() -> Any:
    from src.services.firebase_service import async_db  # noqa: PLC0415

    return async_db


async def aget_procedures(
    ids: Iterable[str], *, _db: Any = None
) -> list[ProcedureRecord]:
    """Records in the order asked for; unknown ids are skipped."""
    db = _db or _default_db()
    wanted = list(dict.fromkeys(ids))
    collection = db.collection(PROCEDURES_COLLECTION)
    snapshots = await asyncio.gather(
        *(collection.document(vid).get() for vid in wanted)
    )
    return [
        ProcedureRecord.model_validate(snapshot.to_dict())
        for snapshot in snapshots
        if snapshot.exists
    ]


async def aget_procedure(
    vorgang_id: str, *, _db: Any = None
) -> Optional[ProcedureRecord]:
    found = await aget_procedures([vorgang_id], _db=_db)
    return found[0] if found else None


def procedure_ids_of(payload: dict[str, Any]) -> list[str]:
    """The procedures a chunk payload is linked to."""
    return [str(v) for v in payload.get("vorgang_ids") or []]


async def aprocedures_for_chunks(
    payloads: Iterable[dict[str, Any]], *, _db: Any = None
) -> dict[str, list[ProcedureSummary]]:
    """chunk_key → summaries of the chunk's procedures (all looked up at once)."""
    payloads = list(payloads)
    ids = {vid for p in payloads for vid in procedure_ids_of(p)}
    records = {r.vorgang_id: r for r in await aget_procedures(sorted(ids), _db=_db)}
    return {
        str(p.get("chunk_key")): [
            records[vid].summary() for vid in procedure_ids_of(p) if vid in records
        ]
        for p in payloads
    }


def _view_filter(vorgang_id: str, source_type: str, party_id: Optional[str]) -> Filter:
    must = [
        FieldCondition(key="vorgang_ids", match=MatchValue(value=vorgang_id)),
        FieldCondition(key="source_type", match=MatchValue(value=source_type)),
    ]
    if party_id is not None:
        # Votes belong to every party that voted and Drucksachen to every
        # Fraktion that tabled them (``party_ids``); a speech to its speaker's.
        key = "party_id" if source_type == "parliamentary_speech" else "party_ids"
        must.append(FieldCondition(key=key, match=MatchValue(value=party_id)))
    return Filter(must=must)


async def _linked(
    client: Any, vorgang_id: str, source_type: str, party_id: Optional[str], limit: int
) -> list[dict[str, Any]]:
    """The oldest ``limit`` linked chunks; a speech's dip twin is dropped
    when its op version is there (twins are fetched, then collapsed)."""
    fetch = limit * 2 if source_type == "parliamentary_speech" else limit
    points, _ = await client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=_view_filter(vorgang_id, source_type, party_id),
        limit=fetch,
        order_by=OrderBy(key="publish_date", direction=Direction.ASC),
        with_payload=PayloadSelectorExclude(exclude=_VIEW_PAYLOAD_EXCLUDE),
        with_vectors=False,
    )
    payloads = [dict(p.payload or {}) for p in points]
    if source_type == "parliamentary_speech":
        payloads = dedup_prefer_op(payloads)
    return payloads[:limit]


async def aget_procedure_view(
    vorgang_id: str,
    *,
    party_id: Optional[str] = None,
    limit: int = 60,
    _db: Any = None,
    _client: Any = None,
) -> Optional[ProcedureView]:
    """The procedure and up to ``limit`` linked chunks per kind, oldest first."""
    procedure = await aget_procedure(vorgang_id, _db=_db)
    if procedure is None:
        return None
    client = _client if _client is not None else _get_qdrant()
    votes, speeches, documents = await asyncio.gather(
        _linked(client, vorgang_id, "vote_record", party_id, limit),
        _linked(client, vorgang_id, "parliamentary_speech", party_id, limit),
        _linked(client, vorgang_id, "drucksache", party_id, limit),
    )
    return ProcedureView(
        procedure=procedure, votes=votes, speeches=speeches, documents=documents
    )


_MAX_KIND_FETCH = 200


async def asearch_procedures(
    query: str,
    *,
    limit: int = 5,
    party_id: Optional[str] = None,
    kinds: Optional[Iterable[ProcedureKind]] = None,
    _db: Any = None,
    _client: Any = None,
    _embed_fn: Any = None,
) -> list[tuple[ProcedureSummary, float]]:
    """Procedures whose profile matches the query, best first; with a
    party, those it tabled (alone or with others). ``kinds`` keeps e.g.
    legislation and motions and drops procedural items (elections, rulings
    on order), which are half of all procedures."""
    wanted = set(kinds) if kinds is not None else None
    if wanted is not None and not wanted:
        return []
    # The profile payload has no kind, so a kind filter over-fetches and
    # widens until the page is full or the hits run out.
    fetch = limit if wanted is None else limit * 3
    while True:
        hits = await retrieve(
            query,
            source_type="procedure",
            party_ids_contains=party_id,
            limit=fetch,
            with_scores=True,
            _client=_client,
            _embed_fn=_embed_fn,
        )
        scored = [hit for hit in hits if isinstance(hit, tuple)]
        ids = [vid for payload, _ in scored for vid in procedure_ids_of(payload)[:1]]
        records = {r.vorgang_id: r for r in await aget_procedures(ids, _db=_db)}
        out: list[tuple[ProcedureSummary, float]] = []
        for payload, score in scored:
            vid = next(iter(procedure_ids_of(payload)), None)
            if vid in records and (wanted is None or records[vid].kind in wanted):
                out.append((records[vid].summary(), score))
        if len(out) >= limit or len(hits) < fetch or fetch >= _MAX_KIND_FETCH:
            return out[:limit]
        fetch = min(fetch * 4, _MAX_KIND_FETCH)


async def asearch_procedure_documents(
    query: str,
    *,
    vorgang_id: Optional[str] = None,
    limit: int = 5,
    _client: Any = None,
    _embed_fn: Any = None,
) -> list[dict[str, Any]]:
    """Drucksache chunks for the query: Vorblatt, Anträge and committee
    reports, optionally inside one procedure."""
    return _payloads(
        await retrieve(
            query,
            source_type="drucksache",
            vorgang_id=vorgang_id,
            limit=limit,
            _client=_client,
            _embed_fn=_embed_fn,
        )
    )


def _payloads(hits: Any) -> list[dict[str, Any]]:
    return [hit for hit in hits if isinstance(hit, dict)]
