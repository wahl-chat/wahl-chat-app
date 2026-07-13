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
