# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
SSE chat endpoint — POST /api/v1/chat.

Streams Vercel AI SDK data-stream protocol:
  f  — message frame init
  0  — text delta (token)
  8  — data annotation (sources_ready, responding_parties, party_complete, etc.)
  e  — step finish
  d  — final summary
  [DONE] — stream end

Multi-party: SERIALIZED (one party at a time).
Limitation: true concurrent multiplexed streaming is deferred.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    """POST /api/v1/chat — streams Vercel AI SDK data-stream protocol over SSE.

    Returns text/event-stream with x-vercel-ai-ui-message-stream: v1 header.
    All V1 named chat events preserved as data annotations (type 8).
    Request body validated via Pydantic (FastAPI returns 422 on invalid input).
    The FastAPI Request is passed to generate_chat_stream for disconnect detection.
    """
    return StreamingResponse(
        with_heartbeat(generate_chat_stream(body, request)),
        headers=_SSE_HEADERS,
    )
