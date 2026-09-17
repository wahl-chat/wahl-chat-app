# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
PledgeTracker suggestion-service unit tests (Qdrant/Firestore/LLM all faked).

Tests defined here:
  - test_retrieve_applies_qdrant_filters: the Qdrant call carries the hard
    filters (source_type=pledge_record, tenant party_id, the caller-provided
    region_path) and the precomputed query vector.
  - test_gate_keeps_only_relevant_candidates: only judged-relevant pledge ids
    are hydrated, retrieval order preserved; the gate prompt carries the query
    and every candidate description.
  - test_gate_dropping_everything_returns_none: all candidates dropped → None
    (the UI then renders no PledgeTracker entry point) and Firestore hydration
    is never called.
  - test_gate_error_keeps_all_candidates: an LLM failure degrades to the
    pre-gate behavior (all candidates kept) instead of hiding data.
  - test_gate_invalid_indices_keep_all_candidates: out-of-range output is
    treated like a failure.
  - test_missing_region_path_defaults_to_de: callers without a region_path
    (older contexts) fall back to ["DE"].
"""

from __future__ import annotations

import pytest

import src.pledge_tracker_service as service
from src.models.pledge_tracker import PledgeRecord
from src.models.structured_outputs import PledgeRelevanceOutput


class _FakeGate:
    """Stands in for the structured-output roster call inside the gate."""

    def __init__(self, indices: list[int] | None = None, error: bool = False):
        self._indices = indices if indices is not None else []
        self._error = error
        self.prompts: list[str] = []

    async def __call__(self, messages) -> PledgeRelevanceOutput:  # noqa: ANN001
        self.prompts.append(messages[0].content)
        if self._error:
            raise RuntimeError("gate LLM unavailable")
        return PledgeRelevanceOutput(relevant_indices=self._indices)


def _patch_gate(monkeypatch: pytest.MonkeyPatch, gate: _FakeGate) -> None:
    async def _fn(messages):  # noqa: ANN001, ANN202
        return await gate(messages)

    monkeypatch.setattr(service, "_default_structured_output", _fn)


def _record(pledge_id: str) -> PledgeRecord:
    return PledgeRecord(
        pledge_id=pledge_id,
        party_id="cdu",
        claim=f"Claim {pledge_id}",
        normalized_summary=f"Zusammenfassung {pledge_id}",
        region_path=["DE", "DE-ST"],
        region="DE-ST",
        timeline_events=[],
    )


def _wire(monkeypatch: pytest.MonkeyPatch, payloads: list[dict]) -> dict:
    """Fake retrieve/hydration; record retrieve kwargs + hydrated ids."""
    calls: dict = {"hydrated": None, "retrieve_kwargs": None}

    # Async, like the real retrieve() — a sync fake would keep passing even if
    # the service stopped awaiting it.
    async def fake_retrieve(query: str, **kwargs):
        calls["retrieve_kwargs"] = {"query": query, **kwargs}
        return payloads

    async def fake_pledges(pledge_ids: list[str]):
        calls["hydrated"] = pledge_ids
        return [_record(pid) for pid in pledge_ids]

    monkeypatch.setattr(service, "retrieve", fake_retrieve)
    monkeypatch.setattr(service, "aget_pledges_by_ids", fake_pledges)
    return calls


_THREE_PAYLOADS = [
    {"pledge_id": "p-verkehr", "text": "Versprechen: A14 fertigstellen"},
    {"pledge_id": "p-wirtschaft", "text": "Versprechen: Vergabeschwellen erhöhen"},
    {"pledge_id": "p-polizei", "text": "Versprechen: 6.400 Polizisten"},
]


async def test_retrieve_applies_qdrant_filters(monkeypatch) -> None:
    """The Qdrant call carries the hard filters and the precomputed vector."""
    calls = _wire(monkeypatch, [_THREE_PAYLOADS[0]])
    _patch_gate(monkeypatch, _FakeGate(indices=[1]))

    result = await service.aretrieve_pledge_tracker_suggestions(
        query="A14 Ausbau",
        party_id="cdu",
        region_path=["DE", "DE-ST"],
        query_vector=[0.1, 0.2],
    )

    assert result is not None
    assert result.party_id == "cdu"
    assert calls["retrieve_kwargs"] == {
        "query": "A14 Ausbau",
        "source_type": "pledge_record",
        "party_id": "cdu",
        "region_path": ["DE", "DE-ST"],
        "limit": 3,
        "query_vector": [0.1, 0.2],
    }


async def test_gate_keeps_only_relevant_candidates(monkeypatch) -> None:
    """Only judged-relevant ids hydrate, in retrieval order."""
    calls = _wire(monkeypatch, list(_THREE_PAYLOADS))
    gate = _FakeGate(indices=[1, 3])
    _patch_gate(monkeypatch, gate)

    result = await service.aretrieve_pledge_tracker_suggestions(
        query="A14 Ausbau",
        party_id="cdu",
        region_path=["DE", "DE-ST"],
    )

    assert result is not None
    assert calls["hydrated"] == ["p-verkehr", "p-polizei"]
    assert "A14 Ausbau" in gate.prompts[0]
    assert "Vergabeschwellen" in gate.prompts[0]


async def test_gate_dropping_everything_returns_none(monkeypatch) -> None:
    """All candidates dropped → None; hydration is never called."""
    calls = _wire(monkeypatch, list(_THREE_PAYLOADS))
    _patch_gate(monkeypatch, _FakeGate(indices=[]))

    result = await service.aretrieve_pledge_tracker_suggestions(
        query="Außenpolitik",
        party_id="cdu",
        region_path=["DE", "DE-ST"],
    )

    assert result is None
    assert calls["hydrated"] is None


async def test_gate_error_keeps_all_candidates(monkeypatch) -> None:
    """An LLM failure degrades to pre-gate behavior (all candidates kept)."""
    calls = _wire(monkeypatch, list(_THREE_PAYLOADS))
    _patch_gate(monkeypatch, _FakeGate(error=True))

    result = await service.aretrieve_pledge_tracker_suggestions(
        query="A14 Ausbau",
        party_id="cdu",
        region_path=["DE", "DE-ST"],
    )

    assert result is not None
    assert calls["hydrated"] == ["p-verkehr", "p-wirtschaft", "p-polizei"]


async def test_gate_invalid_indices_keep_all_candidates(monkeypatch) -> None:
    """Out-of-range gate output is treated like a failure (all kept)."""
    calls = _wire(monkeypatch, list(_THREE_PAYLOADS))
    _patch_gate(monkeypatch, _FakeGate(indices=[0, 7]))

    result = await service.aretrieve_pledge_tracker_suggestions(
        query="A14 Ausbau",
        party_id="cdu",
        region_path=["DE", "DE-ST"],
    )

    assert result is not None
    assert calls["hydrated"] == ["p-verkehr", "p-wirtschaft", "p-polizei"]


async def test_missing_region_path_defaults_to_de(monkeypatch) -> None:
    """Callers without a region_path (older contexts) fall back to ["DE"]."""
    calls = _wire(monkeypatch, [_THREE_PAYLOADS[0]])
    _patch_gate(monkeypatch, _FakeGate(indices=[1]))

    await service.aretrieve_pledge_tracker_suggestions(
        query="Mindestlohn",
        party_id="spd",
        region_path=None,
    )

    assert calls["retrieve_kwargs"]["region_path"] == ["DE"]
