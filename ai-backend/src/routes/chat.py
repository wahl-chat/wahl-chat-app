# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
SSE chat endpoint — POST /api/v1/chat.

Streams AI SDK v5 UI-message-stream parts (`data: <json>` with a `type`
discriminator, parsed by `@ai-sdk/react` useChat):
  start / start-step         — message frame init
  text-start/-delta/-end     — party answer text blocks
  data-chat_event            — named chat events (sources_ready,
                               responding_parties, party_chunk,
                               party_complete, quick_replies_title, error)
  finish-step / finish       — finish events
  data: [DONE]               — stream terminator

Multi-party: SERIALIZED (one party at a time).
Limitation: true concurrent multiplexed streaming is deferred.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.auth import resolve_user_is_logged_in
from src.chat_service import generate_chat_stream, with_heartbeat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# SSE response headers
# NOTE: Using StreamingResponse (not EventSourceResponse) because generate_chat_stream
# yields pre-framed SSE strings ("data: ...\n\n"). EventSourceResponse would wrap them
# in an extra "data: " prefix, producing double-framed events that break SSE parsers.
# We set X-Accel-Buffering: no manually (sse-starlette sets it automatically for
# EventSourceResponse, but StreamingResponse does not — nginx/Cloudflare requires it).
_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


class ChatRequestDto(BaseModel):
    session_id: str
    context_id: str
    user_message: str
    party_ids: list[str]
    user_is_logged_in: bool = False
    chat_history: list = []


@router.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequestDto):
    """POST /api/v1/chat — streams AI SDK v5 UI-message-stream parts over SSE.

    Returns text/event-stream with x-vercel-ai-ui-message-stream: v1 header.
    All V1 named chat events are preserved inside `data-chat_event` parts.
    Request body validated via Pydantic (FastAPI returns 422 on invalid input).
    The FastAPI Request is passed to generate_chat_stream for disconnect detection.

    Auth: verification is OPTIONAL (anonymous users are served normally), but
    the body's user_is_logged_in flag (premium LLM selection) is honored only
    when the request carries a valid `Authorization: Bearer <Firebase ID token>`.
    """
    body.user_is_logged_in = resolve_user_is_logged_in(
        request, body.user_is_logged_in, "chat"
    )
    return StreamingResponse(
        with_heartbeat(generate_chat_stream(body, request)),
        headers=_SSE_HEADERS,
    )
