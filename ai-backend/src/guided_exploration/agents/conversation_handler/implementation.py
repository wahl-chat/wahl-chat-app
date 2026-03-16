# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of conversation handler agent."""

import asyncio
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import StreamingAgent
from src.guided_exploration.agents.conversation_handler.interface import (
    ConversationHandlerInput,
    ConversationHandlerOutput,
)
from src.guided_exploration.agents.conversation_handler.prompts import (
    CONVERSATION_PROMPT,
    STREAMING_SYSTEM_PROMPT,
    STREAMING_USER_PROMPT,
    SYSTEM_PROMPT,
    ConversationLLMOutput,
    format_chunks_for_conversation,
    format_conversation_history,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.streaming import StreamChunk

logger = logging.getLogger(__name__)

# Streaming configuration
WORDS_PER_CHUNK = 5
CHUNK_DELAY = 0.05  # 50ms between chunks


class ConversationHandlerAgent(
    StreamingAgent[ConversationHandlerInput, ConversationHandlerOutput]
):
    """
    Handles follow-up questions within a leaf conversation.

    Uses the resolved knowledge and conversation history to
    generate contextual responses. Supports streaming for
    progressive display in the UI.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "conversation_handler"

    async def stream(
        self, input: ConversationHandlerInput
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream response generation for the follow-up question.

        Yields chunks with 'response' section marker.
        """
        # Generate full response first
        output = await self._generate_response(input)

        # Stream the response
        async for chunk in self._stream_text(output.response, "response"):
            yield chunk

        # Final chunk
        yield StreamChunk(content="", is_final=True, section=None)

    async def execute(
        self, input: ConversationHandlerInput
    ) -> ConversationHandlerOutput:
        """
        Non-streaming execution returning complete response.
        """
        return await self._generate_response(input)

    def stream_from_llm(self, input: ConversationHandlerInput) -> AsyncIterator[str]:
        """
        Stream directly from LLM with party markers for frontend display.

        Uses streaming prompts that include [PARTY:id] markers and
        inline citations. Yields raw text chunks from the LLM.
        """
        messages = self._build_streaming_messages(input)
        return self._llm.stream(messages=messages, temperature=0.5)

    def _build_streaming_messages(self, input: ConversationHandlerInput) -> list:
        """Build messages for streaming LLM response with party markers."""
        knowledge = input.resolved_knowledge

        # Build party context for system prompt
        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        # Build system message with streaming prompt
        system_prompt = STREAMING_SYSTEM_PROMPT.format(party_context=party_context)

        # Get subtopic name from leaf_id
        subtopic_name = input.leaf_id.split(".")[-1].replace("_", " ").title()

        # Format chunks for direct source access (primary source of truth)
        chunks_text, _ = format_chunks_for_conversation(
            knowledge.party_chunks, input.parties_info
        )

        # Build user message with context
        user_prompt = STREAMING_USER_PROMPT.format(
            subtopic_name=subtopic_name,
            message=input.message,
            conversation_history=format_conversation_history(
                input.conversation_history
            ),
            chunks=chunks_text,
        )

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    async def _generate_response(
        self, input: ConversationHandlerInput
    ) -> ConversationHandlerOutput:
        """Generate response using LLM."""
        knowledge = input.resolved_knowledge

        # Build party context for system prompt
        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        # Build system message
        system_prompt = SYSTEM_PROMPT.format(party_context=party_context)

        # Get subtopic name from leaf_id
        subtopic_name = input.leaf_id.split(".")[-1].replace("_", " ").title()

        # Format chunks for direct source access (primary source of truth)
        chunks_text, _ = format_chunks_for_conversation(
            knowledge.party_chunks, input.parties_info
        )

        # Build user message with context
        user_prompt = CONVERSATION_PROMPT.format(
            subtopic_name=subtopic_name,
            message=input.message,
            conversation_history=format_conversation_history(
                input.conversation_history
            ),
            chunks=chunks_text,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Generate structured output
        llm_output: ConversationLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=ConversationLLMOutput,
            temperature=0.5,  # Balanced for conversational tone
        )

        # Map cited_sources to actual Citation objects
        citation_map = {c.id: c for c in knowledge.citation_pool}
        citations: list[Citation] = [
            citation_map[cid] for cid in llm_output.cited_sources if cid in citation_map
        ]

        return ConversationHandlerOutput(
            response=llm_output.response,
            citations=citations,
            suggested_followups=llm_output.suggested_followups,
        )

    async def _stream_text(self, text: str, section: str) -> AsyncIterator[StreamChunk]:
        """Stream text in word chunks."""
        words = text.split()

        for i in range(0, len(words), WORDS_PER_CHUNK):
            chunk = " ".join(words[i : i + WORDS_PER_CHUNK])
            if i + WORDS_PER_CHUNK < len(words):
                chunk += " "

            yield StreamChunk(content=chunk, section=section, is_final=False)
            await asyncio.sleep(CHUNK_DELAY)
