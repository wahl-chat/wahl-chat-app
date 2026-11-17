# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""procedure_service against in-memory Firestore and Qdrant stand-ins."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import src.services.procedure_service as service

_RECORDS = json.loads((Path(__file__).parent / "fixtures" / "procedures" / "records.json").read_text())


class _Snap:
    def __init__(self, data: dict | None) -> None:
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> dict | None:
        return self._data


class _Doc:
    def __init__(self, data: dict | None) -> None:
        self._data = data

    async def get(self) -> _Snap:
        return _Snap(self._data)


class _Collection:
    def __init__(self, docs: dict[str, dict]) -> None:
        self._docs = docs

    def document(self, doc_id: str) -> _Doc:
        return _Doc(self._docs.get(doc_id))


class FakeDb:
    def __init__(self) -> None:
        self.docs = {r["vorgang_id"]: r for r in _RECORDS}

    def collection(self, name: str) -> _Collection:
        assert name == "procedures"
        return _Collection(self.docs)


class _Point:
    def __init__(self, payload: dict) -> None:
        self.payload = payload


class FakeQdrant:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = payloads
        self.filters: list[Any] = []

    async def scroll(self, collection_name, scroll_filter, limit, order_by, with_payload, with_vectors):  # noqa: ANN001
        self.filters.append(scroll_filter)
        assert order_by.key == "publish_date"
        wanted = {c.key: c.match.value for c in scroll_filter.must}
        found = [
            p for p in self.payloads
            if all(
                (v in p.get(k, [])) if isinstance(p.get(k), list) else p.get(k) == v
                for k, v in wanted.items()
            )
        ]
        found.sort(key=lambda p: p["publish_date"])
        return [_Point(p) for p in found[:limit]], None


def _chunk(kind: str, day: str, **extra: Any) -> dict:
    return {"source_type": kind, "vorgang_ids": ["320784"], "publish_date": day,
            "chunk_key": f"{kind}:{day}", **extra}


@pytest.mark.asyncio
async def test_unknown_ids_are_skipped_not_errors() -> None:
    db = FakeDb()
    assert await service.aget_procedure("nope", _db=db) is None
    found = await service.aget_procedures(["338366", "nope", "320784"], _db=db)
    assert [r.vorgang_id for r in found] == ["338366", "320784"]


@pytest.mark.asyncio
async def test_view_orders_linked_chunks_and_filters_by_party() -> None:
    qdrant = FakeQdrant([
        _chunk("parliamentary_speech", "2025-03-18", party_id="spd"),
        _chunk("parliamentary_speech", "2025-03-13", party_id="cdu"),
        _chunk("vote_record", "2025-03-18", party_ids=["cdu", "spd"]),
        _chunk("drucksache", "2025-03-10", party_id="_all", party_ids=["cdu", "spd"]),
    ])
    view = await service.aget_procedure_view("320784", _db=FakeDb(), _client=qdrant)
    assert view is not None
    assert [s["publish_date"] for s in view.speeches] == ["2025-03-13", "2025-03-18"]
    assert len(view.votes) == 1 and len(view.documents) == 1
    assert any(s.name == "3. Beratung" for s in view.procedure.stages)
    spd = await service.aget_procedure_view("320784", party_id="spd", _db=FakeDb(), _client=qdrant)
    assert spd is not None and [s["party_id"] for s in spd.speeches] == ["spd"]
    assert len(spd.votes) == 1  # votes match by party_ids
    assert len(spd.documents) == 1  # a joint bill is each tabling party's


@pytest.mark.asyncio
async def test_view_of_an_unknown_procedure_is_none() -> None:
    assert await service.aget_procedure_view("nope", _db=FakeDb(), _client=FakeQdrant([])) is None


@pytest.mark.asyncio
async def test_procedures_for_chunks() -> None:
    out = await service.aprocedures_for_chunks(
        [{"chunk_key": "a", "vorgang_ids": ["338366", "nope"]}, {"chunk_key": "b"}], _db=FakeDb()
    )
    assert [s.vorgang_id for s in out["a"]] == ["338366"] and out["b"] == []
    assert out["a"][0].milestones


@pytest.mark.asyncio
async def test_search_hydrates_profile_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_retrieve(query, **kw):  # noqa: ANN001, ANN003
        assert kw["source_type"] == "procedure"
        assert kw["party_ids_contains"] is None
        return [({"vorgang_ids": ["338366"]}, 0.8), ({"vorgang_ids": ["gone"]}, 0.7)]

    monkeypatch.setattr(service, "retrieve", fake_retrieve)
    hits = await service.asearch_procedures("Alkoholsteuer", _db=FakeDb())
    assert [(s.vorgang_id, score) for s, score in hits] == [("338366", 0.8)]


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["overview", "all", "drill_down"])
async def test_document_strategies(monkeypatch: pytest.MonkeyPatch, strategy: str) -> None:
    calls: list[dict] = []

    async def fake_retrieve(query, **kw):  # noqa: ANN001, ANN003
        calls.append(kw)
        section = kw.get("doc_section") or ["any"]
        return [{"doc_section": section[-1], "vorgang_ids": ["338366"], "n": i} for i in range(kw["limit"])]

    monkeypatch.setattr(service, "retrieve", fake_retrieve)
    out = await service.asearch_procedure_documents("q", limit=4, strategy=strategy)
    sections = [c.get("doc_section") for c in calls]
    if strategy == "overview":
        assert sections == [["overview", "report"]]
    elif strategy == "all":
        assert sections == [None]
    else:
        assert sections == [["overview", "report"], ["body"]]
        assert calls[1]["vorgang_id"] == "338366"  # drill into the best overview hit's procedure
        assert [d["doc_section"] for d in out] == ["report", "report", "body", "body"]


def test_the_default_reads_overview_and_reports() -> None:
    assert service.DEFAULT_STRATEGY == "overview"


@pytest.mark.asyncio
async def test_view_drops_the_dip_twin_of_an_op_speech() -> None:
    twin = {"speech_key": "de-20-214-anna-muster-top1", "source_item_id": "x"}
    qdrant = FakeQdrant([
        _chunk("parliamentary_speech", "2025-03-18", source="dip", **{**twin, "source_item_id": "d"}),
        _chunk("parliamentary_speech", "2025-03-18", source="op", **{**twin, "source_item_id": "o"}),
    ])
    view = await service.aget_procedure_view("320784", _db=FakeDb(), _client=qdrant)
    assert view is not None and [s["source"] for s in view.speeches] == ["op"]
