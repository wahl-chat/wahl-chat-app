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

from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.models.procedures import (
    DrucksacheStrategy,
    ProcedureRecord,
    ProcedureSummary,
    ProcedureView,
)
from src.retrieve import COLLECTION_NAME, _get_qdrant, retrieve
from wahlchat_common.procedures import PROCEDURES_COLLECTION

logger = logging.getLogger(__name__)

# The winner of the S1–S3 comparison (ADR-0013).
DEFAULT_STRATEGY: DrucksacheStrategy = "S1"
_VIEW_SCROLL_PAGE = 256
# Speech payloads carry a sentence-by-sentence video map; a view needs none of it.
_VIEW_PAYLOAD_EXCLUDE = ["meta.sentence_map"]


def _default_db() -> Any:
    from src.services.firebase_service import async_db  # noqa: PLC0415

    return async_db


async def aget_procedures(ids: Iterable[str], *, _db: Any = None) -> list[ProcedureRecord]:
    """Records in the order asked for; unknown ids are skipped."""
    db = _db or _default_db()
    wanted = list(dict.fromkeys(ids))
    collection = db.collection(PROCEDURES_COLLECTION)
    snapshots = await asyncio.gather(*(collection.document(vid).get() for vid in wanted))
    return [
        ProcedureRecord.model_validate(snapshot.to_dict())
        for snapshot in snapshots
        if snapshot.exists
    ]


async def aget_procedure(vorgang_id: str, *, _db: Any = None) -> Optional[ProcedureRecord]:
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
        # Votes belong to every party that voted; the rest to one.
        key = "party_ids" if source_type == "vote_record" else "party_id"
        must.append(FieldCondition(key=key, match=MatchValue(value=party_id)))
    return Filter(must=must)


async def _linked(
    client: Any, vorgang_id: str, source_type: str, party_id: Optional[str], limit: int
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    offset = None
    while len(payloads) < limit:
        points, offset = await client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=_view_filter(vorgang_id, source_type, party_id),
            limit=min(_VIEW_SCROLL_PAGE, limit - len(payloads)),
            offset=offset,
            with_payload={"exclude": _VIEW_PAYLOAD_EXCLUDE},
            with_vectors=False,
        )
        payloads.extend(dict(p.payload or {}) for p in points)
        if offset is None:
            break
    return sorted(
        payloads,
        key=lambda p: (str(p.get("publish_date") or ""), str(p.get("chunk_key") or "")),
    )


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
    return ProcedureView(procedure=procedure, votes=votes, speeches=speeches, documents=documents)


async def asearch_procedures(
    query: str,
    *,
    limit: int = 5,
    party_id: Optional[str] = None,
    _db: Any = None,
    _client: Any = None,
    _embed_fn: Any = None,
) -> list[tuple[ProcedureSummary, float]]:
    """Procedures whose profile matches the query, best first."""
    hits = await retrieve(
        query,
        source_type="procedure",
        party_id=party_id,
        limit=limit,
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
        if vid in records:
            out.append((records[vid].summary(), score))
    return out


async def asearch_procedure_documents(
    query: str,
    *,
    vorgang_id: Optional[str] = None,
    limit: int = 5,
    strategy: DrucksacheStrategy = DEFAULT_STRATEGY,
    _client: Any = None,
    _embed_fn: Any = None,
) -> list[dict[str, Any]]:
    """Drucksache chunks for the query, as the shipped strategy reaches them.

    S1: overview chunks (Vorblatt, Anträge) only. S2: overview and body in one
    ranking. S3: overview first, then the body of the procedure asked for
    (``vorgang_id``) or of the procedure the best overview hit belongs to.
    """
    common: dict[str, Any] = {
        "source_type": "drucksache",
        "vorgang_id": vorgang_id,
        "_client": _client,
        "_embed_fn": _embed_fn,
    }
    if strategy == "S2":
        return _payloads(await retrieve(query, limit=limit, **common))
    overview = _payloads(await retrieve(query, limit=limit, doc_section="overview", **common))
    if strategy == "S1":
        return overview
    target = vorgang_id or next((vid for p in overview for vid in procedure_ids_of(p)), None)
    if target is None:
        return overview
    body_common = {**common, "vorgang_id": target}
    body = _payloads(await retrieve(query, limit=limit, doc_section="body", **body_common))
    # Half the slots for the overview, the rest for the drill-down.
    keep = max(1, limit // 2)
    return [*overview[:keep], *body[: limit - keep]]


def _payloads(hits: Any) -> list[dict[str, Any]]:
    return [hit for hit in hits if isinstance(hit, dict)]
