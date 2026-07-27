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

import json
from typing import Any

import httpx
import pytest

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
    assert [c["party_id"] for c in completes] == ["spd", "cdu"], (
        "SERIALIZED multi-party: one successful party_complete per responder in order"
    )
    assert all(c["status"]["indicator"] == "success" for c in completes)
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
    assert events[-1] == "[DONE]"
