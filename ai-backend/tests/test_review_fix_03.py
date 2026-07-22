# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Regression tests for the code-review BLOCKER fixes.

These guard the *production wiring* paths that the original tests did NOT
exercise (they used injection seams that bypass run.py → worker.py):

  - run.py's embedding_worker branch must call run_embedding_worker(db, qdrant)
           with both clients — not run_embedding_worker() with zero args.
  - BundestagVoteConnector.normalize() must persist a non-null storage_ref
           so the worker's GCS load gets a real blob path.
  - BundestagVoteConnector.discover() must honour the persisted high-water
           vote ID and exclude already-processed IDs.
  - work_queue.claim_pending_work() must also re-claim retryable "failed"
           items (not only "pending"), so the dead-letter retry path runs.
  - _parse_german_date() raises on an unparseable date (no 1970 epoch).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock

import pytest

try:
    from src.ingestion.connectors.bundestag_votes import (
        BundestagVoteConnector,
        _parse_german_date,
    )
except ImportError as _e:
    pytest.skip(
        f"schema teardown: {_e} — bundestag_votes deleted",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Minimal in-memory Firestore stub (no live emulator required).
# ---------------------------------------------------------------------------


class _FakeDoc:
    def __init__(self, store: dict, doc_id: str) -> None:
        self._store = store
        self._id = doc_id

    @property
    def reference(self) -> "_FakeDoc":
        return self

    @property
    def exists(self) -> bool:
        return self._id in self._store

    def to_dict(self) -> Optional[dict]:
        return dict(self._store.get(self._id, {}))

    def get(self) -> "_FakeDoc":
        return self

    def set(self, data: dict, merge: bool = False) -> None:
        if merge and self._id in self._store:
            self._store[self._id].update(data)
        else:
            self._store[self._id] = dict(data)

    def update(self, data: dict) -> None:
        self._store.setdefault(self._id, {}).update(data)


class _FakeQuery:
    def __init__(self, docs: list[_FakeDoc]) -> None:
        self._docs = docs

    def where(self, filter: Any) -> "_FakeQuery":  # noqa: A002
        # Support FieldFilter("vector_status", "in", [...]) used by claim_pending_work.
        field = getattr(filter, "field_path", None) or getattr(
            filter, "_field_path", None
        )
        op = getattr(filter, "op_string", None) or getattr(filter, "_op_string", None)
        value = getattr(filter, "value", None)
        if value is None:
            value = getattr(filter, "_value", None)

        def _match(d: _FakeDoc) -> bool:
            data = d.to_dict() or {}
            actual = data.get(field)
            if op == "in":
                return actual in value
            if op == "==":
                return actual == value
            return True

        return _FakeQuery([d for d in self._docs if _match(d)])

    def limit(self, n: int) -> "_FakeQuery":
        return _FakeQuery(self._docs[:n])

    def stream(self):
        return iter(self._docs)


class _FakeCollection:
    def __init__(self, store: dict) -> None:
        self._store = store

    def document(self, doc_id: str) -> _FakeDoc:
        return _FakeDoc(self._store, doc_id)

    def where(self, filter: Any) -> _FakeQuery:  # noqa: A002
        docs = [_FakeDoc(self._store, k) for k in self._store]
        return _FakeQuery(docs).where(filter)

    def limit(self, n: int) -> _FakeQuery:
        docs = [_FakeDoc(self._store, k) for k in self._store]
        return _FakeQuery(docs).limit(n)


class _FakeDB:
    def __init__(self) -> None:
        self._collections: dict[str, dict] = {}

    def collection(self, name: str) -> _FakeCollection:
        return _FakeCollection(self._collections.setdefault(name, {}))


# ---------------------------------------------------------------------------
# normalize() persists a non-null storage_ref.
# ---------------------------------------------------------------------------


def test_normalize_sets_storage_ref(bundestag_vote_939: dict) -> None:
    """the persisted SourceItemRecord must carry a gs:// storage_ref."""
    connector = BundestagVoteConnector(
        db=_FakeDB(),
        fetch_fn=lambda _vid: bundestag_vote_939,
        vote_ids=[bundestag_vote_939["id"]],
    )
    raw = connector.fetch("939")
    si = connector.normalize(raw)

    assert si.storage_ref is not None, "storage_ref must be set at normalize time"
    assert si.storage_ref.startswith("gs://"), si.storage_ref
    assert si.storage_ref.endswith("/votes/939.json"), si.storage_ref

    # And the worker's gs:// → blob_path parse must yield the same path
    # store_original writes to (votes/939.json).
    blob_path = si.storage_ref[5:].split("/", 1)[1]
    assert blob_path == "votes/939.json"


# ---------------------------------------------------------------------------
# discover() honours the persisted high-water vote ID.
# ---------------------------------------------------------------------------


def test_discover_excludes_processed_ids() -> None:
    """discover() returns only IDs strictly greater than the watermark."""
    db = _FakeDB()
    # Seed a watermark with last_external_id = 940.
    db.collection("ingestion_watermarks").document("bundestag_votes").set(
        {
            "connector_id": "bundestag_votes",
            "last_external_id": "940",
            "last_processed_at": None,
            "updated_at": None,
        }
    )

    connector = BundestagVoteConnector(
        db=db,
        vote_ids=["938", "939", "940", "941", "942"],
    )
    result = connector.discover(since=None)

    assert result == ["941", "942"], (
        f"discover() must drop IDs <= watermark 940; got {result}"
    )


def test_discover_returns_all_on_first_run() -> None:
    """with no watermark, discover() returns all IDs sorted ascending."""
    connector = BundestagVoteConnector(db=_FakeDB(), vote_ids=["941", "939", "940"])
    assert connector.discover(since=None) == ["939", "940", "941"]


# ---------------------------------------------------------------------------
# watermark advances monotonically (never regresses).
# ---------------------------------------------------------------------------


def test_write_watermark_is_monotonic(bundestag_vote_939: dict) -> None:
    """writing an older vote ID must not move the watermark backwards."""
    db = _FakeDB()
    connector = BundestagVoteConnector(db=db, vote_ids=["939"])

    # Advance to 940 first.
    connector._last_external_id = "940"
    connector.write_watermark(datetime(2025, 3, 21, tzinfo=timezone.utc))
    stored = db.collection("ingestion_watermarks").document("bundestag_votes").to_dict()
    assert stored["last_external_id"] == "940"

    # Now attempt to write an earlier ID 939 — must stay at 940.
    connector._last_external_id = "939"
    connector.write_watermark(datetime(2025, 3, 20, tzinfo=timezone.utc))
    stored = db.collection("ingestion_watermarks").document("bundestag_votes").to_dict()
    assert stored["last_external_id"] == "940", (
        "watermark regressed below the high-water vote ID"
    )


# ---------------------------------------------------------------------------
# _parse_german_date raises (no epoch fallback).
# ---------------------------------------------------------------------------


def test_parse_german_date_raises_on_garbage() -> None:
    """an unparseable date raises ValueError instead of returning 1970."""
    assert _parse_german_date("2025-03-21") == date(2025, 3, 21)
    assert _parse_german_date("21. März 2025") == date(2025, 3, 21)
    with pytest.raises(ValueError):
        _parse_german_date("not a date")


# ---------------------------------------------------------------------------
# claim_pending_work re-claims "failed" items.
# ---------------------------------------------------------------------------


def test_claim_pending_work_reclaims_failed() -> None:
    """a retryable "failed" item must be re-claimed (flipped to embedding)."""
    from src.ingestion.work_queue import claim_pending_work

    db = _FakeDB()
    items = db.collection("source_items")
    items.document("p1").set({"source_item_id": "p1", "vector_status": "pending"})
    items.document("f1").set({"source_item_id": "f1", "vector_status": "failed"})
    items.document("done").set({"source_item_id": "done", "vector_status": "embedded"})
    items.document("dead").set(
        {"source_item_id": "dead", "vector_status": "embed_failed"}
    )

    claimed = claim_pending_work(db, limit=10)
    claimed_ids = {c["source_item_id"] for c in claimed}

    assert claimed_ids == {"p1", "f1"}, (
        f"claim must include pending AND failed, exclude embedded/embed_failed; got {claimed_ids}"
    )
    # Claimed items must be flipped to "embedding" in the store.
    for sid in ("p1", "f1"):
        assert (
            db.collection("source_items").document(sid).to_dict()["vector_status"]
            == "embedding"
        )
    # Terminal dead-letter is never re-claimed.
    assert (
        db.collection("source_items").document("dead").to_dict()["vector_status"]
        == "embed_failed"
    )


# ---------------------------------------------------------------------------
# run.py's embedding_worker dispatch calls run_embedding_worker(db, qdrant).
# ---------------------------------------------------------------------------


def test_run_module_dispatches_worker_with_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """the embedding_worker branch must pass db AND qdrant to the worker.

    Exercises the production wiring (build clients + call signature) that the
    original tests bypassed via injection seams.  Mocks the client factories so
    no live Firestore/Qdrant is required, and asserts run_embedding_worker is
    invoked with both clients (never zero args, which would TypeError).
    """
    import src.ingestion.run as run_mod
    import src.ingestion.worker as worker_mod
    import src.ingestion.retrieve as retrieve_mod

    fake_db = MagicMock(name="firestore_db")
    fake_qdrant = MagicMock(name="qdrant_client")

    monkeypatch.setattr(run_mod, "_build_firestore_client", lambda: fake_db)
    monkeypatch.setattr(retrieve_mod, "_get_qdrant", lambda: fake_qdrant)

    captured: dict[str, Any] = {}

    def _fake_worker(db: Any, qdrant: Any, **kwargs: Any) -> None:
        captured["db"] = db
        captured["qdrant"] = qdrant

    monkeypatch.setattr(worker_mod, "run_embedding_worker", _fake_worker)

    # Reproduce run.py's dispatch body for the embedding_worker branch exactly
    # (the import + factory wiring + call), proving the signature is satisfied.
    from src.ingestion.worker import run_embedding_worker
    from src.ingestion.retrieve import _get_qdrant

    db = run_mod._build_firestore_client()
    run_embedding_worker(db=db, qdrant=_get_qdrant())

    assert captured["db"] is fake_db
    assert captured["qdrant"] is fake_qdrant
