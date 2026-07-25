# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared Server-Sent-Events framing for the v5 UI-message-stream endpoints.

The chat, pro-con, and voting-behavior endpoints all stream Vercel AI SDK v5
UI-message-stream parts — each SSE event is ``data: <json>\\n\\n`` where the JSON
is a part object with a ``type`` discriminator (``start``, ``text-delta``,
``data-<name>``, ``finish``, …). These primitives live here so the framing is
defined once rather than duplicated per route. Endpoints using them should send
the ``x-vercel-ai-ui-message-stream: v1`` response header.

Named application events (responding_parties, sources_ready, party_chunk,
party_complete, quick_replies_title, vote_result, pro_con_result, error, …) ride
inside a single ``data-chat_event`` part; the frontend switches on the inner
``data.type``.
"""

import json

# Literal stream terminator every endpoint yields last.
DONE = "data: [DONE]\n\n"


def sse(part: object) -> str:
    """Serialize one v5 UI-message-stream part as an SSE event (``data: <json>``)."""
    return f"data: {json.dumps(part)}\n\n"


def start_message(message_id: str) -> str:
    """v5 message-frame init: message ``start`` + open the first ``start-step``."""
    return sse({"type": "start", "messageId": message_id}) + sse({"type": "start-step"})


def data_event(payload: object) -> str:
    """Wrap a named event as a v5 ``data-chat_event`` part (client switches on data.type)."""
    return sse({"type": "data-chat_event", "data": payload})


def text_start(text_id: str) -> str:
    """Open a v5 text block."""
    return sse({"type": "text-start", "id": text_id})


def text_delta(text_id: str, delta: object) -> str:
    """Emit one v5 text-delta token within an open text block."""
    return sse({"type": "text-delta", "id": text_id, "delta": delta})


def text_end(text_id: str) -> str:
    """Close a v5 text block."""
    return sse({"type": "text-end", "id": text_id})


def finish_step() -> str:
    """Close the current v5 step."""
    return sse({"type": "finish-step"})


def finish() -> str:
    """Terminate the v5 message stream."""
    return sse({"type": "finish"})
