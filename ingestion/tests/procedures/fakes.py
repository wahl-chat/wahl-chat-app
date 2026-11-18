# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""In-memory stand-ins for Qdrant, Firestore and DIP used by the procedure tests."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any, Optional

from qdrant_client import models

from ingestion.run import EMBEDDING_DIM


def _get(payload: dict[str, Any], key: str) -> Any:
    value: Any = payload
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(cond: Any, point_id: str, payload: dict[str, Any]) -> bool:
    if isinstance(cond, models.Filter):
        return matches(cond, point_id, payload)
    if isinstance(cond, models.HasIdCondition):
        return point_id in {str(i) for i in cond.has_id}
    if isinstance(cond, models.IsEmptyCondition):
        value = _get(payload, cond.is_empty.key)
        return value is None or value == []
    if isinstance(cond, models.FieldCondition):
        value = _get(payload, cond.key)
        values = value if isinstance(value, list) else [value]
        if isinstance(cond.match, models.MatchValue):
            return cond.match.value in values
        if isinstance(cond.match, models.MatchAny):
            return any(v in cond.match.any for v in values)
        if cond.range is not None:
            if value is None:
                return False
            bound = str(value)[:10]
            gte = getattr(cond.range, "gte", None)
            lt = getattr(cond.range, "lt", None)
            if gte is not None and bound < str(gte)[:10]:
                return False
            if lt is not None and bound >= str(lt)[:10]:
                return False
            return True
    raise NotImplementedError(type(cond))


def matches(
    flt: Optional[models.Filter], point_id: str, payload: dict[str, Any]
) -> bool:
    if flt is None:
        return True
    if flt.must and not all(_matches(c, point_id, payload) for c in flt.must):
        return False
    if flt.must_not and any(_matches(c, point_id, payload) for c in flt.must_not):
        return False
    if flt.should and not any(_matches(c, point_id, payload) for c in flt.should):
        return False
    return True


class _Point:
    def __init__(self, point_id: str, payload: dict[str, Any]) -> None:
        self.id = point_id
        self.payload = payload


class FakeQdrant:
    def __init__(self) -> None:
        self.points: dict[str, dict[str, Any]] = {}
        self.upserts: list[list[str]] = []
        self.deletes: list[list[str]] = []
        self.payload_writes: list[tuple[dict[str, Any], list[str]]] = []
        self.fail_upsert_for: set[str] = set()

    def add(self, point_id: str, payload: dict[str, Any]) -> None:
        self.points[point_id] = copy.deepcopy(payload)

    def scroll(
        self,
        collection_name: str,
        scroll_filter=None,
        limit: int = 10,
        offset=None,
        with_payload: Any = True,
        with_vectors: bool = False,
    ):
        ids = [
            pid
            for pid in sorted(self.points)
            if matches(scroll_filter, pid, self.points[pid])
        ]
        start = int(offset or 0)
        page = ids[start : start + limit]
        nxt = start + limit if start + limit < len(ids) else None
        return [_Point(pid, copy.deepcopy(self.points[pid])) for pid in page], nxt

    def count(self, collection_name: str, count_filter=None, exact: bool = True):
        n = sum(1 for pid, p in self.points.items() if matches(count_filter, pid, p))
        return type("Count", (), {"count": n})()

    def upsert(
        self, collection_name: str, points: list[Any], wait: bool = True
    ) -> None:
        for point in points:
            if point.payload.get("source_parent_key") in self.fail_upsert_for:
                raise RuntimeError("upsert failed")
        self.upserts.append([str(p.id) for p in points])
        for point in points:
            self.points[str(point.id)] = copy.deepcopy(point.payload)

    def delete(
        self, collection_name: str, points_selector: Any, wait: bool = True
    ) -> None:
        ids = [str(i) for i in points_selector.points]
        self.deletes.append(ids)
        for pid in ids:
            self.points.pop(pid, None)

    def set_payload(
        self,
        collection_name: str,
        payload: dict[str, Any],
        points: list[Any],
        key: str | None = None,
        wait: bool = True,
    ) -> None:
        selected = points.points if hasattr(points, "points") else points
        ids = [str(i) for i in selected]
        self.payload_writes.append((copy.deepcopy(payload), ids))
        for pid in ids:
            if pid in self.points:
                target = self.points[pid]
                if key is not None:
                    target = target.setdefault(key, {})
                target.update(copy.deepcopy(payload))


class _Hit:
    def __init__(self, value: Any, count: int) -> None:
        self.value, self.count = value, count


def _facet(
    self: "FakeQdrant",
    collection_name: str,
    key: str,
    facet_filter=None,
    limit: int = 10,
    exact: bool = True,
):
    from collections import Counter

    counts: Counter[Any] = Counter()
    for pid, payload in self.points.items():
        if matches(facet_filter, pid, payload):
            value = _get(payload, key)
            for v in value if isinstance(value, list) else [value]:
                if v is not None:
                    counts[v] += 1
    return type(
        "Facet", (), {"hits": [_Hit(v, n) for v, n in counts.most_common(limit)]}
    )()


def _retrieve(
    self: "FakeQdrant",
    collection_name: str,
    ids: list[Any],
    with_payload: Any = True,
    with_vectors: bool = False,
):
    return [
        _Point(str(i), copy.deepcopy(self.points[str(i)]))
        for i in ids
        if str(i) in self.points
    ]


FakeQdrant.facet = _facet  # type: ignore[attr-defined]
FakeQdrant.retrieve = _retrieve  # type: ignore[attr-defined]


class FakeEmbed:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[int] = []
        self.fail = fail

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise RuntimeError("embedding down")
        self.calls.append(len(texts))
        return [[0.0] * EMBEDDING_DIM for _ in texts]


class _Snapshot:
    def __init__(self, doc_id: str, data: Optional[dict[str, Any]]) -> None:
        self.id = doc_id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> Optional[dict[str, Any]]:
        return copy.deepcopy(self._data)


class _DocRef:
    def __init__(self, db: "FakeFirestore", collection: str, doc_id: str) -> None:
        self._db, self._collection, self.id = db, collection, doc_id

    def get(self) -> _Snapshot:
        return _Snapshot(self.id, self._db.data.get(self._collection, {}).get(self.id))

    def set(self, data: dict[str, Any], merge: bool = False) -> None:
        docs = self._db.data.setdefault(self._collection, {})
        if merge and self.id in docs:
            docs[self.id].update(copy.deepcopy(data))
        else:
            docs[self.id] = copy.deepcopy(data)

    def update(self, data: dict[str, Any]) -> None:
        docs = self._db.data.setdefault(self._collection, {})
        if self.id not in docs:
            raise KeyError(self.id)
        docs[self.id].update(copy.deepcopy(data))


class _Query:
    def __init__(
        self, db: "FakeFirestore", collection: str, filters: list[tuple[str, str, Any]]
    ) -> None:
        self._db, self._collection, self._filters = db, collection, filters

    def where(
        self, field: str = "", op: str = "", value: Any = None, *, filter: Any = None
    ) -> "_Query":
        if filter is not None:
            field, op, value = filter.field_path, filter.op_string, filter.value
        return _Query(self._db, self._collection, [*self._filters, (field, op, value)])

    def stream(self):
        for doc_id, data in sorted(self._db.data.get(self._collection, {}).items()):
            if all(_where(data, *f) for f in self._filters):
                yield _Snapshot(doc_id, data)


def _where(data: dict[str, Any], field: str, op: str, value: Any) -> bool:
    got = data.get(field)
    if op == "==":
        return got == value
    if op == "array_contains":
        return value in (got or [])
    if op == "array_contains_any":
        return any(v in (got or []) for v in value)
    if op == "in":
        return got in value
    raise NotImplementedError(op)


class _Collection(_Query):
    def __init__(self, db: "FakeFirestore", name: str) -> None:
        super().__init__(db, name, [])

    def document(self, doc_id: str) -> _DocRef:
        return _DocRef(self._db, self._collection, doc_id)


class _Batch:
    def __init__(self) -> None:
        self._ops: list[Any] = []

    def set(self, ref: _DocRef, data: dict[str, Any], merge: bool = False) -> None:
        self._ops.append(lambda: ref.set(data, merge=merge))

    def update(self, ref: _DocRef, data: dict[str, Any]) -> None:
        self._ops.append(lambda: ref.update(data))

    def commit(self) -> None:
        for op in self._ops:
            op()


class FakeFirestore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, dict[str, Any]]] = {}

    def collection(self, name: str) -> _Collection:
        return _Collection(self, name)

    def get_all(self, refs: list[_DocRef]):
        return [ref.get() for ref in refs]

    def batch(self) -> _Batch:
        return _Batch()


class FakeDip:
    """Serves the fixtures; ``fail`` makes the named reads raise."""

    def __init__(
        self, vorgaenge: dict[str, Any], positions: dict[str, Any], **extra: Any
    ) -> None:
        self._vorgaenge = vorgaenge
        self._positions = positions
        self.plenary: dict[int, dict[str, str]] = extra.get("plenary", {})
        self.core: dict[int, set[str]] = extra.get("core", {})
        self.updated: dict[int, set[str]] = extra.get("updated", {})
        self.days: dict[date, list[dict[str, Any]]] = extra.get("days", {})
        self.activities: dict[str, list[dict[str, Any]]] = extra.get("activities", {})
        self.drucksachen: dict[str, list[str]] = extra.get("drucksachen", {})
        self.texts: dict[str, dict[str, Any]] = extra.get("texts", {})
        self.fail: set[str] = set(extra.get("fail", set()))
        self.updated_since: list[str] = []
        self.text_reads: list[str] = []

    def _check(self, name: str) -> None:
        if name in self.fail:
            raise RuntimeError(f"DIP {name} failed")

    def plenary_vorgang_types(self, wahlperiode: int) -> dict[str, str]:
        self._check("plenary")
        return self.plenary.get(wahlperiode, {})

    def vorgang_ids_of_types(self, wahlperiode: int, types) -> set[str]:
        self._check("core")
        return self.core.get(wahlperiode, set())

    def updated_vorgang_ids(self, wahlperiode: int, since: str) -> set[str]:
        self._check("updated")
        self.updated_since.append(since)
        return self.updated.get(wahlperiode, set())

    def vorgaenge(self, ids) -> dict[str, Any]:
        self._check("vorgaenge")
        return {i: self._vorgaenge[i] for i in ids if i in self._vorgaenge}

    def positions(self, ids) -> dict[str, list[Any]]:
        self._check("positions")
        return {i: self._positions.get(i, []) for i in ids}

    def positions_on(self, day: date) -> list[dict[str, Any]]:
        self._check("positions_on")
        return self.days.get(day, [])

    def protocol_activities(self, protocol_number: str) -> list[dict[str, Any]]:
        self._check(f"activities:{protocol_number}")
        return self.activities.get(protocol_number, [])

    def drucksache_vorgaenge(self, numbers) -> dict[str, list[str]]:
        self._check("drucksachen")
        return {n: self.drucksachen[n] for n in numbers if n in self.drucksachen}

    def drucksache_texts(self, numbers) -> dict[str, dict[str, Any]]:
        self.text_reads.extend(numbers)
        self._check("texts")
        return {n: self.texts[n] for n in numbers if n in self.texts}
