# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
SSE pro-con endpoint — POST /api/v1/pro-con.

Streams a pro/con perspective as a v5 ``data-chat_event`` part (inner type
"pro_con_result"), then finish + [DONE]. On error: a ``data-chat_event`` with
inner type "error", then [DONE]. Framing helpers live in src.sse.
"""

import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from src.auth import verify_optional_bearer_token
from src.chatbot_async import generate_pro_con_perspective
from src.sse import DONE, data_event, finish
from src.utils import GENERIC_ERROR_MESSAGE
from src.firebase_service import aget_party_for_context
from src.models.chat import Message
from src.models.context import DEFAULT_CONTEXT_ID
from src.models.dtos import (
    ProConPerspectiveDto,
    ProConPerspectiveRequestDto,
    Status,
    StatusIndicator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# Protocol header on top of sse-starlette's own SSE headers.
_STREAM_HEADERS = {"x-vercel-ai-ui-message-stream": "v1"}
_SSE_PING_SECONDS = 15


@router.post("/pro-con")
async def pro_con_endpoint(request: Request, body: ProConPerspectiveRequestDto):
    """POST /api/v1/pro-con — streams the pro/con result as a v5 data part then [DONE].

    Pydantic validates the request body.

    Auth: verification is OPTIONAL (no 401s). This route currently carries no
    privileged body flag, but the optional Bearer token is verified for parity
    with /chat and /voting-behavior so future premium gating inherits it.
    """
    # Verified claims (or None for anonymous) — no privileged flag consumes
    # them yet; kept so the auth contract is uniform across the SSE routes.
    _ = verify_optional_bearer_token(request)

    async def stream():
        try:
            context_id = body.context_id or DEFAULT_CONTEXT_ID
            party = await aget_party_for_context(context_id, body.party_id)
            if party is None:
                raise ValueError(
                    f"Party {body.party_id} not found in context {context_id}"
                )

            last_user_message = Message(role="user", content=body.last_user_message)
            last_assistant_message = Message(
                role="assistant", content=body.last_assistant_message
            )
            chat_history = [last_user_message, last_assistant_message]

            pro_con_perspective = await generate_pro_con_perspective(
                chat_history, party, body.context_id
            )

            response_dto = ProConPerspectiveDto(
                request_id=body.request_id,
                message=pro_con_perspective,
                status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
            )

            yield data_event({"type": "pro_con_result", **response_dto.model_dump()})
            yield finish()
            yield DONE

        except Exception as e:
            logger.error(
                f"Error generating pro/con perspective for party {body.party_id}: {e}",
                exc_info=True,
            )
            # Generic client-facing message only — full detail is logged above.
            yield data_event({"type": "error", "message": GENERIC_ERROR_MESSAGE})
            yield DONE

    return EventSourceResponse(
        stream(), headers=_STREAM_HEADERS, ping=_SSE_PING_SECONDS
    )
