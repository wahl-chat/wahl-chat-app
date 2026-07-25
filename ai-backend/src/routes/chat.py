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

from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from src.chat_service import generate_chat_stream, with_heartbeat
from src.models.chat import Role

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


# Server-side bounds on the PUBLIC, unauthenticated chat endpoint. Every field
# flows into LLM prompts, so an unbounded body is a cost / context-overflow /
# memory vector. V1 enforced a 500-char user message (ChatUserMessageDto) that
# the SSE migration dropped; restore it and bound the list inputs + history
# depth. Invalid input is rejected by FastAPI with 422 before reaching the LLM.
_MAX_USER_MESSAGE_CHARS = 500
_MAX_PARTY_IDS = 20  # largest seeded roster (Baden-Württemberg) is 19
_MAX_HISTORY_MESSAGES = 100
# Per-turn and aggregate content ceilings. Capping only the list length leaves a
# history of 100 turns each carrying unbounded content — still an unbounded body
# and an unbounded prompt. These are abuse guards (a hostile client cannot post a
# multi-megabyte history), sized well above any real conversation, not UX limits.
_MAX_HISTORY_TURN_CHARS = 10_000
_MAX_HISTORY_TOTAL_CHARS = 300_000


class ChatHistoryTurn(BaseModel):
    """Route-specific history turn — ONLY the fields the pipeline actually reads
    (role, content, party_id; see build_chat_history_string). The output-side
    Message fields (sources, quick_replies, rag_query, id, current_chat_title) are
    intentionally NOT modelled: they are server-generated, must not be trusted from
    the client, and must never be re-fed into the prompt or allocated unbounded.
    Unknown fields are ignored (Pydantic default) so a client that still posts full
    Message objects keeps working — only these three are kept, and content is
    bounded per turn."""

    role: Role
    content: str = Field(max_length=_MAX_HISTORY_TURN_CHARS)
    party_id: Optional[str] = Field(default=None, max_length=200)


class ChatRequestDto(BaseModel):
    session_id: str = Field(max_length=200)
    context_id: str = Field(max_length=200)
    user_message: str = Field(max_length=_MAX_USER_MESSAGE_CHARS)
    party_ids: list[str] = Field(default_factory=list, max_length=_MAX_PARTY_IDS)
    chat_history: list[ChatHistoryTurn] = Field(
        default_factory=list, max_length=_MAX_HISTORY_MESSAGES
    )

    @field_validator("chat_history")
    @classmethod
    def _bound_total_history_chars(
        cls, turns: list[ChatHistoryTurn]
    ) -> list[ChatHistoryTurn]:
        """Bound aggregate history content, not just per-turn — 100 turns each just
        under the per-turn cap would otherwise still be a ~1 MB prompt."""
        total = sum(len(t.content) for t in turns)
        if total > _MAX_HISTORY_TOTAL_CHARS:
            raise ValueError(
                f"chat_history total content {total} exceeds "
                f"{_MAX_HISTORY_TOTAL_CHARS} chars"
            )
        return turns


@router.post("/chat")
async def chat_endpoint(request: Request, body: ChatRequestDto):
    """POST /api/v1/chat — streams AI SDK v5 UI-message-stream parts over SSE.

    Returns text/event-stream with x-vercel-ai-ui-message-stream: v1 header.
    All V1 named chat events are preserved inside `data-chat_event` parts.
    Request body validated via Pydantic (FastAPI returns 422 on invalid input).
    The FastAPI Request is passed to generate_chat_stream for disconnect detection.

    Auth: verification is OPTIONAL (anonymous users are served normally).
    Premium LLM selection is derived server-side inside generate_chat_stream from
    the request's token (a valid, non-anonymous `Authorization: Bearer <Firebase
    ID token>`) — never from the client, so the request carries no such flag.
    """
    return StreamingResponse(
        with_heartbeat(generate_chat_stream(body, request)),
        headers=_SSE_HEADERS,
    )
