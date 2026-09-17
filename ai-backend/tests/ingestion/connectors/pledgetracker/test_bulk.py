# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Bulk-runner unit tests (pure helpers plus the reconcile delete path, which is
driven with fake stores; the API plumbing is exercised via the stub demo run).

Tests defined here:
  - test_last_activity_orders_never_touched_first: no activity → epoch, so new
    pledges outrank previously attempted ones in the batch ordering.
  - test_last_activity_counts_failed_attempts: pledgetracker_last_attempted_at
    advances the ordering key, so a recently failed pledge yields its batch
    slot to pledges with older activity.
  - test_stale_pledge_ids_flags_only_missing: reconcile deletes exactly the
    store ids absent from the registry.
  - test_reconcile_retires_only_out_of_registry_pledges: an edited/removed row
    is retired from both stores while registry members survive.
  - test_reconcile_leaves_other_regions_alone: a pledge outside the registry's
    regions is never touched.
  - test_reconcile_refuses_implausible_mass_retirement: pointing at the wrong
    (or a truncated) registry is refused instead of deleting the collection.
  - test_reconcile_force_allows_mass_retirement: the same run proceeds when
    the retirement is explicitly intended.
  - test_guard_allows_emulator_outside_prod / _prod_without_emulator /
    _refuses_remote_dev_without_flag: accidental-write default.
  - test_allow_remote_clears_emulator_host_for_dev: --allow-remote must win
    over a leftover FIRESTORE_EMULATOR_HOST from .env / the Makefile.
"""

from __future__ import annotations

import os

import pytest

from src.ingestion.connectors.pledgetracker.bulk import (
    ReconcileBlocked,
    _guard_firestore_target,
    _last_activity,
    _stale_pledge_ids,
    reconcile_registry,
)
from src.ingestion.connectors.pledgetracker.registry import PledgeInput


def test_last_activity_orders_never_touched_first() -> None:
    """A pledge with no recorded activity sorts before any touched pledge."""
    untouched = _last_activity({})
    checked = _last_activity({"last_checked_at": "2026-01-01T00:00:00+00:00"})
    assert untouched < checked


def test_last_activity_counts_failed_attempts() -> None:
    """The ordering key is the max of successful check and failed attempt."""
    failed_recently = _last_activity(
        {
            "last_checked_at": "2026-01-01T00:00:00+00:00",
            "pledgetracker_last_attempted_at": "2026-02-01T00:00:00+00:00",
        }
    )
    checked_later = _last_activity({"last_checked_at": "2026-01-15T00:00:00+00:00"})
    assert failed_recently > checked_later


def test_stale_pledge_ids_flags_only_missing() -> None:
    """Ids in the stores but not in the registry are stale; the rest are kept."""
    assert _stale_pledge_ids({"a", "b"}, ["a", "b", "c"]) == {"c"}
    assert _stale_pledge_ids({"a"}, []) == set()


# ---------------------------------------------------------------------------
# reconcile_registry — fake stores (deletes are recorded, never executed)
# ---------------------------------------------------------------------------


class _FakePoint:
    def __init__(self, point_id: int, pledge_id: str) -> None:
        self.id = point_id
        self.payload = {"pledge_id": pledge_id}


class _FakeQdrant:
    """Returns the configured points in one page; records the filter + deletes."""

    def __init__(self, points: list[_FakePoint]) -> None:
        self._points = points
        self.deleted_point_ids: list[int] = []
        self.scroll_filter = None

    def scroll(self, **kwargs):  # type: ignore[no-untyped-def]
        self.scroll_filter = kwargs["scroll_filter"]
        return (self._points, None)

    def delete(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.deleted_point_ids.extend(kwargs["points_selector"].points)


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class _FakeDocRef:
    def __init__(self, collection: _FakeCollection, doc_id: str) -> None:
        self._collection = collection
        self._doc_id = doc_id

    def delete(self) -> None:
        self._collection.deleted_doc_ids.append(self._doc_id)


class _FakeCollection:
    def __init__(self, docs: dict[str, dict]) -> None:
        self._docs = docs
        self.deleted_doc_ids: list[str] = []

    def stream(self) -> list[_FakeSnapshot]:
        return [_FakeSnapshot(doc_id, data) for doc_id, data in self._docs.items()]

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self, doc_id)


class _FakeDb:
    def __init__(self, docs: dict[str, dict]) -> None:
        self.pledges = _FakeCollection(docs)

    def collection(self, name: str) -> _FakeCollection:
        assert name == "pledges"
        return self.pledges


def _pledge(pledge_id: str, bundesland: str | None = "Sachsen-Anhalt") -> PledgeInput:
    return PledgeInput(
        claim=f"claim {pledge_id}",
        pledge_date="2021-03-27",
        pledge_author="CDU",
        bundesland=bundesland,
        pledge_id=pledge_id,
    )


def test_reconcile_retires_only_out_of_registry_pledges() -> None:
    """A row edited or removed from the registry is retired from both stores."""
    qdrant = _FakeQdrant([_FakePoint(1, "keep"), _FakePoint(2, "gone")])
    db = _FakeDb(
        {
            "keep": {"region": "DE-ST"},
            "gone": {"region": "DE-ST"},
        }
    )

    points_deleted, docs_deleted = reconcile_registry(
        qdrant,  # type: ignore[arg-type]
        db,
        [_pledge("keep")],
    )

    assert (points_deleted, docs_deleted) == (1, 1)
    assert qdrant.deleted_point_ids == [2]
    assert db.pledges.deleted_doc_ids == ["gone"]


def test_reconcile_leaves_other_regions_alone() -> None:
    """Out-of-scope pledges survive: one registry never retires another's."""
    qdrant = _FakeQdrant([_FakePoint(1, "keep")])
    db = _FakeDb({"keep": {"region": "DE-ST"}, "federal": {"region": "DE"}})

    points_deleted, docs_deleted = reconcile_registry(
        qdrant,  # type: ignore[arg-type]
        db,
        [_pledge("keep")],
    )

    assert (points_deleted, docs_deleted) == (0, 0)
    assert db.pledges.deleted_doc_ids == []
    # The Qdrant half relies on the server-side region filter carrying the scope.
    region_conditions = [
        condition
        for condition in qdrant.scroll_filter.must  # type: ignore[union-attr]
        if getattr(condition, "key", None) == "region"
    ]
    assert region_conditions[0].match.any == ["DE-ST"]


def test_reconcile_refuses_implausible_mass_retirement() -> None:
    """The wrong (or a truncated) registry is refused, not obeyed."""
    qdrant = _FakeQdrant([_FakePoint(1, "keep")])
    db = _FakeDb(
        {f"stored-{i}": {"region": "DE-ST"} for i in range(4)}
        | {"keep": {"region": "DE-ST"}}
    )

    with pytest.raises(ReconcileBlocked):
        reconcile_registry(qdrant, db, [_pledge("keep")])  # type: ignore[arg-type]

    assert qdrant.deleted_point_ids == []
    assert db.pledges.deleted_doc_ids == []


def test_reconcile_force_allows_mass_retirement() -> None:
    """An intended bulk retirement still goes through with force."""
    qdrant = _FakeQdrant([_FakePoint(1, "keep")])
    db = _FakeDb(
        {f"stored-{i}": {"region": "DE-ST"} for i in range(4)}
        | {"keep": {"region": "DE-ST"}}
    )

    _, docs_deleted = reconcile_registry(
        qdrant,  # type: ignore[arg-type]
        db,
        [_pledge("keep")],
        force=True,
    )

    assert docs_deleted == 4
    assert sorted(db.pledges.deleted_doc_ids) == [f"stored-{i}" for i in range(4)]


# ---------------------------------------------------------------------------
# _guard_firestore_target — accidental-write default + --allow-remote
# ---------------------------------------------------------------------------


def test_guard_allows_emulator_outside_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    _guard_firestore_target()


def test_guard_allows_prod_without_emulator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    _guard_firestore_target()


def test_guard_refuses_remote_dev_without_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(RuntimeError, match="FIRESTORE_EMULATOR_HOST"):
        _guard_firestore_target()


def test_allow_remote_clears_emulator_host_for_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--allow-remote must reach deployed ENV Firestore, not the leftover emulator."""
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")
    _guard_firestore_target(allow_remote=True)
    assert "FIRESTORE_EMULATOR_HOST" not in os.environ
