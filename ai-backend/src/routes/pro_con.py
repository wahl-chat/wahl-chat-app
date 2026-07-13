# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
SSE pro-con endpoint — POST /api/v1/pro-con.

Streams a pro/con perspective as a Vercel AI SDK data annotation (type 8)
with type "pro_con_result", then [DONE].

On error: yields an error annotation (type "error") then [DONE].
"""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from src.chatbot_async import generate_pro_con_perspective
from src.chat_service import with_heartbeat
from src.firebase_service import aget_party_by_id
from src.models.chat import Message
from src.models.dtos import (
    ProConPerspectiveDto,
    Status,
    StatusIndicator,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# SSE headers
# NOTE: StreamingResponse is used (not EventSourceResponse) because the generator
# yields pre-framed "data: ...\n\n" strings; EventSourceResponse would double-wrap them.
_SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "x-vercel-ai-ui-message-stream": "v1",
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
}


class ProConRequestDto(BaseModel):
    request_id: str
    party_id: str
    last_assistant_message: str
    last_user_message: str
    context_id: Optional[str] = None


@router.post("/pro-con")
async def pro_con_endpoint(body: ProConRequestDto):
    """POST /api/v1/pro-con — streams pro/con result as data annotation then [DONE].

    V1 event map: pro_con_perspective_complete → 8 type=pro_con_result.
    Error path: yields 8 type=error then [DONE] (matches V1 error DTO pattern).
    Pydantic validates request body.
    """

    async def stream():
        try:
            party = await aget_party_by_id(body.party_id)
            if party is None:
                raise ValueError(f"Party {body.party_id} not found")

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

            # 8: data annotation — pro_con_result
            # (replaces V1 socket_emit("pro_con_perspective_complete", ...))
            yield f"data: 8{json.dumps({'type': 'pro_con_result', **response_dto.model_dump()})}\n\n"
            yield f"data: d{json.dumps({'finishReason': 'stop', 'usage': {}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(
                f"Error generating pro/con perspective for party {body.party_id}: {e}",
                exc_info=True,
            )
            # Error path: yield error annotation then [DONE] (V1 error pattern)
            yield f"data: 8{json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(with_heartbeat(stream()), headers=_SSE_HEADERS)
