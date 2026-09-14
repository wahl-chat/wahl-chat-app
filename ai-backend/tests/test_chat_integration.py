# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""End-to-end SSE integration scenarios with mocked Qdrant + LLM.

Each test drives the real FastAPI app in-process (ASGI transport, real routes,
real EventSourceResponse framing, real generate_chat_stream orchestration) with
the same external-I/O fakes as the smoke test (tests/conftest.py patch_chat_io:
retrieval returns a deterministic manifesto payload, the LLM streams fixed
tokens, Firestore is faked). Covered:

  1. single-party response incl. citations, EMPTY conversation history
  2. single-party response incl. citations, NON-EMPTY conversation history
  3. multi-party responses with non-empty conversation history
  4. pro-con perspective of one party after a multi-party turn
  5. comparison response
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessageChunk

_CONTEXT_ID = "bundestagswahl-2025"

_HISTORY = [
    {"role": "user", "content": "Was plant ihr für den Klimaschutz?"},
    {
        "role": "assistant",
        "content": "Die SPD setzt auf erneuerbare Energien.",
        "party_id": "spd",
    },
]


@pytest.fixture()
def app():
    # Imported lazily so patch_chat_io's monkeypatches are active first.
    from src.app import app as _app

    return _app


def _chat_body(**overrides: Any) -> dict:
    body = {
        "session_id": "integration-session",
        "context_id": _CONTEXT_ID,
        "user_message": "Was ist die Position zum Klimaschutz?",
        "party_ids": ["spd"],
        "chat_history": [],
    }
    body.update(overrides)
    return body


async def _drain(app, path: str, body: dict) -> list[Any]:
    """POST an SSE route and return the parsed data payloads (JSON where valid)."""
    events: list[Any] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        async with client.stream("POST", path, json=body) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    events.append("[DONE]")
                    break
                try:
                    events.append(json.loads(payload))
                except json.JSONDecodeError:
                    events.append(payload)
    return events


def _chat_events(events: list[Any], inner_type: str) -> list[dict]:
    return [
        e["data"]
        for e in events
        if isinstance(e, dict)
        and e.get("type") == "data-chat_event"
        and e["data"].get("type") == inner_type
    ]


def _assert_single_party_answer(events: list[Any], party_id: str = "spd") -> None:
    """Common assertions: citations present, answer text streamed, success end."""
    ready = _chat_events(events, "sources_ready")
    assert ready, "sources_ready must be emitted before the answer"
    sources = ready[0]["sources"]
    assert sources, "the answer must carry citations"
    assert all(s.get("url") for s in sources), f"citations need URLs: {sources!r}"
    deltas = [
        e for e in events if isinstance(e, dict) and e.get("type") == "text-delta"
    ]
    assert deltas, "the answer text must stream as v5 text deltas"
    completes = _chat_events(events, "party_complete")
    assert [c["party_id"] for c in completes] == [party_id]
    assert completes[0]["status"]["indicator"] == "success"
    assert completes[0]["complete_message"].strip()
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_single_party_with_citations_empty_history(patch_chat_io, app):
    events = await _drain(app, "/api/v1/chat", _chat_body())
    _assert_single_party_answer(events)
    responding = _chat_events(events, "responding_parties")
    assert responding and responding[0]["party_ids"] == ["spd"]


@pytest.mark.asyncio
async def test_single_party_with_citations_non_empty_history(patch_chat_io, app):
    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(
            user_message="Und wie soll das finanziert werden?",
            chat_history=_HISTORY,
        ),
    )
    _assert_single_party_answer(events)


@pytest.mark.asyncio
async def test_multi_party_responses_non_empty_history(patch_chat_io, app, monkeypatch):
    from src.models.context import ContextParty

    from tests.conftest import _FAKE_PARTY

    cdu = dict(_FAKE_PARTY, party_id="cdu", name="CDU", long_name="CDU Deutschlands")

    async def _two_parties(context_id: str) -> list[ContextParty]:
        return [ContextParty(**_FAKE_PARTY), ContextParty(**cdu)]

    async def _two_targets(*args: Any, **kwargs: Any):
        return (["spd", "cdu"], "Was ist eure Position zum Klimaschutz?", False)

    monkeypatch.setattr("src.chat_service.aget_parties_for_context", _two_parties)
    monkeypatch.setattr("src.chat_service.get_question_targets_and_type", _two_targets)

    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(party_ids=["spd", "cdu"], chat_history=_HISTORY),
    )

    responding = _chat_events(events, "responding_parties")
    assert responding and responding[0]["party_ids"] == ["spd", "cdu"]
    completes = _chat_events(events, "party_complete")
    assert {c["party_id"] for c in completes} == {"spd", "cdu"}, (
        "one successful party_complete per responder (completion order is free)"
    )
    assert all(c["status"]["indicator"] == "success" for c in completes)
    _assert_text_blocks_valid(events)
    # Both parties emit their own citations.
    assert len(_chat_events(events, "sources_ready")) >= 2
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_pro_con_after_multi_party_turn(patch_chat_io, app, monkeypatch):
    from src.models.chat import Message
    from tests.conftest import _FAKE_PARTY

    from src.models.context import ContextParty

    async def _party(context_id: str, party_id: str) -> ContextParty:
        return ContextParty(**_FAKE_PARTY)

    async def _perspective(chat_history, party, context_id) -> Message:
        # The route hands the last user/assistant turn (the multi-party answer)
        # to the generator — echo enough back to prove the wiring.
        assert len(chat_history) == 2
        return Message(
            role="assistant",
            content="Pro: ambitionierter Klimaschutz. Contra: offene Finanzierung.",
            party_id=party.party_id,
        )

    monkeypatch.setattr("src.routes.pro_con.aget_party_for_context", _party)
    monkeypatch.setattr("src.routes.pro_con.generate_pro_con_perspective", _perspective)

    events = await _drain(
        app,
        "/api/v1/pro-con",
        {
            "request_id": "req-1",
            "party_id": "spd",
            "context_id": _CONTEXT_ID,
            "last_user_message": "Wie steht ihr zum Klimaschutz?",
            "last_assistant_message": (
                "SPD: erneuerbare Energien. CDU: Technologieoffenheit."
            ),
        },
    )

    results = _chat_events(events, "pro_con_result")
    assert len(results) == 1
    assert results[0]["status"]["indicator"] == "success"
    assert "Pro:" in results[0]["message"]["content"]
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_comparison_response(patch_chat_io, app, monkeypatch):
    from src.models.context import ContextParty
    from tests.conftest import _FAKE_PARTY

    cdu = dict(_FAKE_PARTY, party_id="cdu", name="CDU", long_name="CDU Deutschlands")

    async def _two_parties(context_id: str) -> list[ContextParty]:
        return [ContextParty(**_FAKE_PARTY), ContextParty(**cdu)]

    async def _comparison_targets(*args: Any, **kwargs: Any):
        return (["spd", "cdu"], "Vergleiche die Klimapositionen von SPD und CDU.", True)

    monkeypatch.setattr("src.chat_service.aget_parties_for_context", _two_parties)
    monkeypatch.setattr(
        "src.chat_service.get_question_targets_and_type", _comparison_targets
    )

    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(
            user_message="Vergleiche SPD und CDU beim Klimaschutz.",
            party_ids=["spd", "cdu"],
            chat_history=_HISTORY,
        ),
    )

    # Comparison answers respond as the wahl.chat assistant.
    responding = _chat_events(events, "responding_parties")
    assert responding and responding[0]["party_ids"] == ["wahl-chat"]
    completes = _chat_events(events, "party_complete")
    assert [c["party_id"] for c in completes] == ["wahl-chat"]
    assert completes[0]["status"]["indicator"] == "success"
    # Comparison citations flow through the SAME typed builder as the
    # single-party path: per-party entries, page taken as built (never +1).
    ready = _chat_events(events, "sources_ready")
    assert ready, "comparison must emit sources_ready"
    sources = ready[-1]["sources"]
    assert sources, "comparison sources must not be empty"
    assert {s.get("party_id") for s in sources} == {"spd", "cdu"}
    assert all(s.get("page") == 1 for s in sources), (
        f"comparison pages must be taken as built (no off-by-one), got "
        f"{[s.get('page') for s in sources]!r}"
    )
    _assert_text_blocks_valid(events)
    assert events[-1] == "[DONE]"


def _assert_text_blocks_valid(events: list[Any]) -> None:
    """Every text-start id has a matching text-end; no delta is unopened or closed."""
    open_ids: set[str] = set()
    closed_ids: set[str] = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        text_id = event.get("id")
        if kind == "text-start":
            assert isinstance(text_id, str)
            assert text_id not in open_ids
            open_ids.add(text_id)
        elif kind == "text-delta":
            assert isinstance(text_id, str)
            assert text_id in open_ids, f"delta for unopened or closed id {text_id}"
            assert text_id not in closed_ids
        elif kind == "text-end":
            assert isinstance(text_id, str)
            assert text_id in open_ids
            open_ids.remove(text_id)
            closed_ids.add(text_id)
    assert not open_ids, f"unclosed text blocks: {open_ids}"


def _install_two_parties(monkeypatch: pytest.MonkeyPatch, *, comparing: bool = False):
    from src.models.context import ContextParty
    from tests.conftest import _FAKE_PARTY

    cdu = dict(_FAKE_PARTY, party_id="cdu", name="CDU", long_name="CDU Deutschlands")

    async def _two_parties(context_id: str) -> list[ContextParty]:
        return [ContextParty(**_FAKE_PARTY), ContextParty(**cdu)]

    async def _two_targets(*args: Any, **kwargs: Any):
        question = (
            "Vergleiche die Klimapositionen von SPD und CDU."
            if comparing
            else "Was ist eure Position zum Klimaschutz?"
        )
        return (["spd", "cdu"], question, comparing)

    monkeypatch.setattr("src.chat_service.aget_parties_for_context", _two_parties)
    monkeypatch.setattr("src.chat_service.get_question_targets_and_type", _two_targets)


def _party_aware_stream(
    *,
    tokens_per_party: int = 5,
    sleep_s: float = 0.0,
    yield_sleep: bool = True,
    fail_party_id: str | None = None,
):
    """Return a generate_streaming_chatbot_response fake keyed by party_id."""

    async def _fake(
        party: Any, *args: Any, **kwargs: Any
    ) -> AsyncIterator[AIMessageChunk]:
        if fail_party_id is not None and party.party_id == fail_party_id:
            raise RuntimeError(f"{fail_party_id} boom")

        async def _gen() -> AsyncIterator[AIMessageChunk]:
            if sleep_s:
                await asyncio.sleep(sleep_s)
            for i in range(tokens_per_party):
                if yield_sleep:
                    await asyncio.sleep(0)
                yield AIMessageChunk(content=f"{party.party_id}{i}")

        return _gen()

    return _fake


@pytest.mark.asyncio
async def test_multi_party_chunks_interleave(patch_chat_io, app, monkeypatch):
    """Concurrent pumps must interleave party_chunk events, not emit one block after another."""
    _install_two_parties(monkeypatch)
    monkeypatch.setattr(
        "src.chat_service.generate_streaming_chatbot_response",
        _party_aware_stream(tokens_per_party=6, yield_sleep=True),
    )

    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(party_ids=["spd", "cdu"], chat_history=_HISTORY),
    )

    chunks = _chat_events(events, "party_chunk")
    party_order = [c["party_id"] for c in chunks]
    assert set(party_order) == {"spd", "cdu"}
    # A serialized drain would emit all of one party, then all of the other.
    first_run = party_order[0]
    first_block_len = 0
    for party_id in party_order:
        if party_id != first_run:
            break
        first_block_len += 1
    assert first_block_len < len(party_order), (
        f"party_chunk events did not interleave: {party_order}"
    )
    _assert_text_blocks_valid(events)
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_multi_party_latency_is_max_not_sum(patch_chat_io, app, monkeypatch):
    """Two 0.3s party streams must finish near the max, not the serial sum."""
    _install_two_parties(monkeypatch)
    monkeypatch.setattr(
        "src.chat_service.generate_streaming_chatbot_response",
        _party_aware_stream(tokens_per_party=1, sleep_s=0.3, yield_sleep=False),
    )

    started = time.monotonic()
    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(party_ids=["spd", "cdu"], chat_history=_HISTORY),
    )
    elapsed = time.monotonic() - started

    completes = _chat_events(events, "party_complete")
    assert {c["party_id"] for c in completes} == {"spd", "cdu"}
    assert all(c["status"]["indicator"] == "success" for c in completes)
    assert elapsed < 0.55, (
        f"multi-party wall clock {elapsed:.2f}s looks serialized (expected ~0.3s)"
    )
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_multi_party_partial_failure(patch_chat_io, app, monkeypatch):
    """One party's generator raising must not prevent the other from completing."""
    _install_two_parties(monkeypatch)
    monkeypatch.setattr(
        "src.chat_service.generate_streaming_chatbot_response",
        _party_aware_stream(tokens_per_party=2, fail_party_id="cdu"),
    )

    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(party_ids=["spd", "cdu"], chat_history=_HISTORY),
    )

    completes = _chat_events(events, "party_complete")
    by_party = {c["party_id"]: c for c in completes}
    assert set(by_party) == {"spd", "cdu"}
    assert by_party["spd"]["status"]["indicator"] == "success"
    assert by_party["cdu"]["status"]["indicator"] == "error"
    _assert_text_blocks_valid(events)
    assert events[-1] == "[DONE]"


@pytest.mark.asyncio
async def test_multi_party_budget_exhaustion_completes_unfinished(
    patch_chat_io, app, monkeypatch
):
    """Budget expiry emits an error party_complete for every unfinished responder."""
    _install_two_parties(monkeypatch)
    monkeypatch.setattr("src.chat_service._CHAT_STREAM_BUDGET_S", 0.05)
    monkeypatch.setattr(
        "src.chat_service.generate_streaming_chatbot_response",
        _party_aware_stream(tokens_per_party=1, sleep_s=2.0, yield_sleep=False),
    )

    events = await _drain(
        app,
        "/api/v1/chat",
        _chat_body(party_ids=["spd", "cdu"], chat_history=_HISTORY),
    )

    completes = _chat_events(events, "party_complete")
    assert {c["party_id"] for c in completes} >= {"spd", "cdu"}
    assert all(c["status"]["indicator"] == "error" for c in completes)
    types = [e.get("type") for e in events if isinstance(e, dict)]
    assert "finish-step" in types and "finish" in types
    assert events[-1] == "[DONE]"
    _assert_text_blocks_valid(events)
