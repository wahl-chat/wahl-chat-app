# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""SSE streaming primitives — thinking events, chat messages, text streams."""

import asyncio
from collections.abc import AsyncIterator
from typing import Literal
from uuid import uuid4

from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    ChatMessageEvent,
    Citation,
    ErrorEvent,
    StreamChunkEvent,
    StreamEndEvent,
    ThinkingEvent,
)

# Inter-chunk delay for the synthetic word-stream path. 50 ms feels live to
# users without flooding the SSE channel.
CHUNK_DELAY = 0.05
WORDS_PER_CHUNK = 5

ThinkingStage = Literal["classifying", "planning", "retrieving", "generating"]
StreamTargetType = Literal[
    "initial_content",
    "followup",
    "analysis",
    "quick_summary",
    "system_message",
]


class StreamingService:
    """Thin async wrapper around the SSE manager for the common event shapes.

    Holds no per-request state — safe to share as a singleton on the facade.
    """

    def __init__(self, sse: SSEManager) -> None:
        self._sse = sse

    async def send_thinking(
        self,
        session_id: str,
        stage: ThinkingStage,
        message: str,
    ) -> None:
        await self._sse.send_to_session(
            session_id,
            ThinkingEvent(stage=stage, message=message),
        )

    async def send_chat_message(
        self,
        session_id: str,
        message: str,
        citations: list[Citation] | None = None,
        can_explore_deeper: bool = False,
        query_id: str | None = None,
        suggested_questions: list[str] | None = None,
    ) -> None:
        await self._sse.send_to_session(
            session_id,
            ChatMessageEvent(
                type="chat_message",
                message_id=str(uuid4()),
                content=message,
                citations=citations or [],
                can_explore_deeper=can_explore_deeper,
                query_id=query_id,
                suggested_questions=suggested_questions or [],
            ),
        )

    async def stream_text(
        self,
        session_id: str,
        content: str,
        stream_id: str,
        target_type: StreamTargetType,
        target_id: str,
        section: str | None = None,
    ) -> None:
        """Synthetic word-stream for already-resolved text.

        Used for canned messages (clarifications, fallbacks, caveats) where
        we want the same animated rendering as a real LLM stream.
        """
        words = content.split()
        chunk_index = 0

        for i in range(0, len(words), WORDS_PER_CHUNK):
            chunk = " ".join(words[i : i + WORDS_PER_CHUNK])
            if i + WORDS_PER_CHUNK < len(words):
                chunk += " "

            await self._sse.send_to_session(
                session_id,
                StreamChunkEvent(
                    stream_id=stream_id,
                    target_type=target_type,
                    target_id=target_id,
                    section=section,
                    chunk=chunk,
                    chunk_index=chunk_index,
                ),
            )
            chunk_index += 1
            await asyncio.sleep(CHUNK_DELAY)

        await self._sse.send_to_session(
            session_id,
            StreamEndEvent(
                stream_id=stream_id,
                target_type=target_type,
                target_id=target_id,
                complete=True,
            ),
        )

    async def stream_from_llm(
        self,
        session_id: str,
        stream_id: str,
        llm_stream: AsyncIterator[str],
        target_type: StreamTargetType,
        target_id: str,
        section: str | None = None,
    ) -> str:
        """Forward LLM chunks to SSE in real time and return the full text."""
        full_text = ""
        chunk_index = 0

        async for chunk in llm_stream:
            full_text += chunk
            await self._sse.send_to_session(
                session_id,
                StreamChunkEvent(
                    stream_id=stream_id,
                    target_type=target_type,
                    target_id=target_id,
                    section=section,
                    chunk=chunk,
                    chunk_index=chunk_index,
                ),
            )
            chunk_index += 1

        await self._sse.send_to_session(
            session_id,
            StreamEndEvent(
                stream_id=stream_id,
                target_type=target_type,
                target_id=target_id,
                complete=True,
            ),
        )

        return full_text

    async def send_error(
        self,
        session_id: str,
        code: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        await self._sse.send_to_session(
            session_id,
            ErrorEvent(
                code=code,
                message=message,
                recoverable=recoverable,
                suggested_action=None,
            ),
        )
