# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
E2E SSE smoke test.

These tests exercise the REAL FastAPI route and the AI SDK v5 UI-message-stream
framing (parts: start / text-delta / data-chat_event / finish / [DONE]).  They
run against the FastAPI app object in-process via httpx.AsyncASGITransport so that
pytest monkeypatching (applied by the conftest patch_chat_io fixture)
replaces only the two external I/O calls — the Qdrant search and the LLM
token stream — without any live API keys or Qdrant service.

Tests:
  - test_chat_sse_smoke: POST /api/v1/chat yields:
      * at least one text delta part (type == 'text-delta')
      * at least one custom data part (type == 'data-chat_event') whose
        inner data.type == 'sources_ready'
      * a terminal '[DONE]'
      * the required SSE headers

  - test_sse_headers: the response carries Content-Type:
    text/event-stream, x-vercel-ai-ui-message-stream: v1, and
    Cache-Control: no-cache, no-transform.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

_CHAT_REQUEST_BODY = {
    "session_id": "smoke-test-session",
    "context_id": "bundestagswahl-2025",
    "user_message": "Was ist die Position der SPD zum Klimaschutz?",
    "party_ids": ["spd"],
    "user_is_logged_in": False,
    "chat_history": [],
}


@pytest.fixture()
def app():
    """Import and return the FastAPI app for in-process ASGI testing.

    Imported lazily here (not at module level) so that the conftest
    patch_chat_io fixture's monkeypatches are already active when the app
    module is first used in the test.  The app import triggers module-level
    Firebase initialisation which is tolerant of missing credentials (it logs
    a warning and continues).
    """
    from src.app import app as _app

    return _app


@pytest.mark.asyncio
async def test_chat_sse_smoke(patch_chat_io, app):
    """POST /api/v1/chat yields at least one v5 text-delta part AND one
    data-chat_event part whose data.type == 'sources_ready', plus a terminal
    '[DONE]'.  SSE headers must be correct.

    Runs in-process via ASGI transport — no live API keys, no Qdrant, no
    Firestore.  The conftest patch_chat_io fixture supplies deterministic
    returns for the two primary external I/O calls (Qdrant search and LLM
    stream) and the auxiliary Firestore / LLM helper calls.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json=_CHAT_REQUEST_BODY,
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", ""), (
                "Missing text/event-stream in Content-Type header"
            )
            assert (
                response.headers.get("x-vercel-ai-ui-message-stream") == "v1"
            ), "Missing x-vercel-ai-ui-message-stream: v1 header"
            assert "no-cache" in response.headers.get("cache-control", ""), (
                "Missing no-cache in Cache-Control header"
            )
            assert "no-transform" in response.headers.get("cache-control", ""), (
                "Missing no-transform in Cache-Control header"
            )

            has_text_delta = False
            has_sources_annotation = False
            has_done = False

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    has_done = True
                    break
                part = json.loads(payload)  # v5: each data: line is a JSON part
                if part.get("type") == "text-delta":
                    has_text_delta = True
                elif part.get("type") == "data-chat_event":
                    if part.get("data", {}).get("type") == "sources_ready":
                        has_sources_annotation = True

            assert has_text_delta, "No v5 text-delta parts received"
            assert has_sources_annotation, (
                "No sources_ready event (data-chat_event part) received"
            )
            assert has_done, "Stream did not end with '[DONE]'"


@pytest.mark.asyncio
async def test_with_heartbeat_emits_keepalive_during_idle():
    """with_heartbeat() interleaves an SSE comment keep-alive when the
    wrapped generator is idle longer than `interval`, while preserving the real
    data frames in order. Protects against corporate-proxy idle timeouts before
    the first LLM token (the failure that motivated the move off WebSockets)."""
    from src.chat_service import with_heartbeat

    async def slow_gen():
        # Idle long enough (relative to interval) to force a heartbeat before the
        # first frame, then emit two real frames back-to-back (no heartbeat).
        await asyncio.sleep(0.06)
        yield 'data: {"type":"text-delta","id":"m1","delta":"Hallo"}\n\n'
        yield "data: [DONE]\n\n"

    chunks = [chunk async for chunk in with_heartbeat(slow_gen(), interval=0.02)]

    # Real frames preserved in order...
    data_frames = [c for c in chunks if c.startswith("data:")]
    assert data_frames == [
        'data: {"type":"text-delta","id":"m1","delta":"Hallo"}\n\n',
        "data: [DONE]\n\n",
    ]
    # ...and at least one keep-alive comment was interleaved during the idle gap.
    assert any(c.startswith(":") for c in chunks), "no heartbeat emitted while idle"


@pytest.mark.asyncio
async def test_sse_headers(patch_chat_io, app):
    """The chat endpoint response carries the required SSE
    anti-buffering headers: Content-Type: text/event-stream,
    x-vercel-ai-ui-message-stream: v1, Cache-Control: no-cache, no-transform.

    Uses the same in-process ASGI transport as test_chat_sse_smoke.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json=_CHAT_REQUEST_BODY,
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", ""), (
                "Missing text/event-stream in Content-Type header"
            )
            assert (
                response.headers.get("x-vercel-ai-ui-message-stream") == "v1"
            ), "Missing x-vercel-ai-ui-message-stream: v1 header"
            assert "no-cache" in response.headers.get("cache-control", ""), (
                "Missing no-cache in Cache-Control header"
            )
            assert "no-transform" in response.headers.get("cache-control", ""), (
                "Missing no-transform in Cache-Control header"
            )


# ===========================================================================
# GDPR cache-gate behavioral tests
# ===========================================================================

_PROPOSED_QUESTION = "Was ist die Position der SPD zum Klimaschutz?"


async def _fake_proposed_questions(party_id: str) -> list[str]:
    return [_PROPOSED_QUESTION]


async def _drain_chat_stream(app, body: dict) -> list[str]:
    """POST /api/v1/chat and return all `data:` payload strings until [DONE]."""
    payloads: list[str] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        async with client.stream(
            "POST",
            "/api/v1/chat",
            json=body,
            headers={"Accept": "text/event-stream"},
        ) as response:
            assert response.status_code == 200
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                payloads.append(payload)
                if payload == "[DONE]":
                    break
    return payloads


@pytest.mark.asyncio
async def test_proposed_question_with_free_text_history_not_cached(
    patch_chat_io, app, monkeypatch
):
    """GDPR cache gate (Art. 9): a proposed question sent MID a non-curated
    (free-text) conversation performs NO cache write — the answer is
    conditioned on user-authored history and must never replay cross-user."""
    write_mock = AsyncMock()
    monkeypatch.setattr(
        "src.chat_service.aget_proposed_questions_for_party",
        _fake_proposed_questions,
    )
    monkeypatch.setattr(
        "src.chat_service.awrite_cached_answer_for_party", write_mock
    )

    body = dict(_CHAT_REQUEST_BODY)
    body["user_message"] = _PROPOSED_QUESTION
    body["chat_history"] = [
        {"role": "user", "content": "Ich habe eine sehr persönliche Meinung dazu."},
        {"role": "assistant", "content": "Danke für deine Nachricht."},
    ]

    payloads = await _drain_chat_stream(app, body)

    assert payloads[-1] == "[DONE]", "stream must still terminate normally"
    write_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_turn_proposed_question_is_cached(
    patch_chat_io, app, monkeypatch
):
    """The legitimate first-turn proposed-question cache is preserved: a single
    proposed-question user turn IS curated, so the answer is written under the
    proposed-question key (regression guard for the cache gate rework)."""
    write_mock = AsyncMock()
    monkeypatch.setattr(
        "src.chat_service.aget_proposed_questions_for_party",
        _fake_proposed_questions,
    )
    monkeypatch.setattr(
        "src.chat_service.awrite_cached_answer_for_party", write_mock
    )

    body = dict(_CHAT_REQUEST_BODY)
    body["user_message"] = _PROPOSED_QUESTION
    body["chat_history"] = []

    payloads = await _drain_chat_stream(app, body)

    assert payloads[-1] == "[DONE]"
    write_mock.assert_awaited_once()
    # (party_id, cache_key, cached_answer) — the key is the question text.
    _party_id, cache_key, _cached = write_mock.await_args.args
    assert cache_key == _PROPOSED_QUESTION


# ===========================================================================
# Mid-stream error path: the client still receives a protocol-valid
# stream — closed text block, error party_complete (generic message only),
# finish events and the [DONE] terminator.
# ===========================================================================


@pytest.mark.asyncio
async def test_mid_stream_error_still_finishes(patch_chat_io, app, monkeypatch):
    """An LLM stream failing MID-generation must not wedge or truncate the SSE
    stream: the open text block is closed, party_complete carries an error
    status WITHOUT internal exception detail, and finish events + [DONE] follow."""
    from langchain_core.messages import AIMessageChunk

    async def _err_stream(*args, **kwargs):
        async def _gen():
            yield AIMessageChunk(content="Hallo")
            raise RuntimeError("boom-internal-detail")

        return _gen()

    monkeypatch.setattr("src.chatbot_async.stream_answer_from_llms", _err_stream)

    payloads = await _drain_chat_stream(app, dict(_CHAT_REQUEST_BODY))

    assert payloads[-1] == "[DONE]", "stream must terminate with [DONE]"
    raw = "\n".join(payloads)
    assert "boom-internal-detail" not in raw, (
        "internal exception detail must never reach the client"
    )

    parts = [json.loads(p) for p in payloads if p != "[DONE]"]
    types = [p.get("type") for p in parts]
    assert types.count("text-start") == types.count("text-end"), (
        "every opened v5 text block must be closed on the error path"
    )
    party_completes = [
        p["data"]
        for p in parts
        if p.get("type") == "data-chat_event"
        and p.get("data", {}).get("type") == "party_complete"
    ]
    assert any(
        (pc.get("status") or {}).get("indicator") == "error"
        for pc in party_completes
    ), "an error party_complete must be emitted"
    assert "finish-step" in types and "finish" in types, (
        "finish events must still be emitted after a mid-stream error"
    )


# ===========================================================================
# Side-channel route-level SSE tests (/api/v1/pro-con, /api/v1/voting-behavior):
# status 200, SSE content type, NO x-vercel-ai-ui-message-stream header (they
# emit legacy code-prefixed frames the frontend hand-parses), [DONE] terminal.
# ===========================================================================

_SIDE_CHANNEL_PARTY = {
    "party_id": "spd",
    "name": "SPD",
    "long_name": "Sozialdemokratische Partei Deutschlands",
    "website_url": "https://www.spd.de",
}


async def _drain_sse(app, path: str, body: dict):
    """POST an SSE endpoint; return (headers, data payload strings until [DONE])."""
    payloads: list[str] = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        async with client.stream(
            "POST", path, json=body, headers={"Accept": "text/event-stream"}
        ) as response:
            assert response.status_code == 200
            headers = response.headers
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                payloads.append(payload)
                if payload == "[DONE]":
                    break
    return headers, payloads


@pytest.mark.asyncio
async def test_pro_con_route_sse(app, monkeypatch):
    """/api/v1/pro-con: 200, text/event-stream, NO v1 stream header, ends [DONE]."""
    from src.models.chat import Message
    from src.models.context import ContextParty

    async def _party(party_id: str):
        return ContextParty(**_SIDE_CHANNEL_PARTY)

    async def _pro_con(chat_history, party, context_id=None):
        return Message(role="assistant", content="Pro: ... Contra: ...")

    monkeypatch.setattr("src.routes.pro_con.aget_party_by_id", _party)
    monkeypatch.setattr(
        "src.routes.pro_con.generate_pro_con_perspective", _pro_con
    )

    headers, payloads = await _drain_sse(
        app,
        "/api/v1/pro-con",
        {
            "request_id": "r1",
            "party_id": "spd",
            "last_assistant_message": "Antwort",
            "last_user_message": "Frage",
        },
    )

    assert "text/event-stream" in headers.get("content-type", "")
    assert "x-vercel-ai-ui-message-stream" not in headers, (
        "pro-con emits legacy code-prefixed frames — it must NOT claim the v5 "
        "UI-message-stream protocol"
    )
    assert payloads[-1] == "[DONE]"
    assert any(p.startswith("8") for p in payloads), (
        "pro_con_result must be emitted as a legacy code-8 frame"
    )


@pytest.mark.asyncio
async def test_voting_behavior_route_sse(app, monkeypatch):
    """/api/v1/voting-behavior: 200, text/event-stream, NO v1 stream header,
    ends [DONE]."""
    from langchain_core.messages import AIMessageChunk
    from src.models.context import ContextParty

    async def _party(party_id: str):
        return ContextParty(**_SIDE_CHANNEL_PARTY)

    async def _rag_query(*args, **kwargs):
        return "verbesserte Anfrage"

    def _retrieve(*args, **kwargs):
        return []

    async def _summary(*args, **kwargs):
        async def _gen():
            yield AIMessageChunk(content="Zusammenfassung.")

        return _gen()

    monkeypatch.setattr("src.routes.voting_behavior.aget_party_by_id", _party)
    monkeypatch.setattr(
        "src.routes.voting_behavior.get_improved_rag_query_voting_behavior",
        _rag_query,
    )
    monkeypatch.setattr("src.routes.voting_behavior.retrieve", _retrieve)
    monkeypatch.setattr(
        "src.routes.voting_behavior.generate_party_vote_behavior_summary",
        _summary,
    )

    headers, payloads = await _drain_sse(
        app,
        "/api/v1/voting-behavior",
        {
            "request_id": "r1",
            "party_id": "spd",
            "last_user_message": "Frage",
            "last_assistant_message": "Antwort",
        },
    )

    assert "text/event-stream" in headers.get("content-type", "")
    assert "x-vercel-ai-ui-message-stream" not in headers, (
        "voting-behavior emits legacy code-prefixed frames — it must NOT claim "
        "the v5 UI-message-stream protocol"
    )
    assert payloads[-1] == "[DONE]"
    assert any(p.startswith("8") for p in payloads), (
        "voting_behavior_complete must be emitted as a legacy code-8 frame"
    )


# ===========================================================================
# Request-DTO bounds (public endpoint hardening)
# ===========================================================================


@pytest.mark.asyncio
async def test_chat_request_rejects_unbounded_input(patch_chat_io, app):
    """The public SSE endpoint must bound user-message length, party count, and
    history depth. V1's ChatUserMessageDto enforced a 500-char cap that the SSE
    migration dropped; each violation must be rejected with 422 before it can
    reach an LLM prompt (cost / context-overflow / memory guard)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=30.0
    ) as client:
        # over-long user message (> 500 chars)
        over_msg = dict(_CHAT_REQUEST_BODY, user_message="x" * 501)
        r = await client.post("/api/v1/chat", json=over_msg)
        assert r.status_code == 422, r.text

        # too many parties (> 20)
        over_parties = dict(
            _CHAT_REQUEST_BODY, party_ids=[f"p{i}" for i in range(21)]
        )
        r = await client.post("/api/v1/chat", json=over_parties)
        assert r.status_code == 422, r.text

        # too-deep history (> 100 turns)
        over_history = dict(
            _CHAT_REQUEST_BODY,
            chat_history=[{"role": "user", "content": "hi"}] * 101,
        )
        r = await client.post("/api/v1/chat", json=over_history)
        assert r.status_code == 422, r.text

        # malformed history entry (missing required Message fields)
        bad_history = dict(_CHAT_REQUEST_BODY, chat_history=[{"foo": "bar"}])
        r = await client.post("/api/v1/chat", json=bad_history)
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_chat_request_accepts_valid_bounded_input(patch_chat_io, app):
    """A well-formed request at the boundary is still accepted (streams 200)."""
    payloads = await _drain_chat_stream(app, dict(_CHAT_REQUEST_BODY))
    assert payloads[-1] == "[DONE]"
