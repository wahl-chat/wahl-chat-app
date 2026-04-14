# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Conversation handler for in-leaf and factual follow-up questions.

Exposes a single entry point, ``stream_from_llm``, which drives the
streaming LLM response with party markers and inline citations. The
response is consumed by the facade and fed back through
``extract_used_citations`` to rebuild the citation list.
"""

from collections.abc import AsyncIterator
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.conversation_handler.interface import (
    ConversationHandlerInput,
)
from src.guided_exploration.agents.conversation_handler.prompts import (
    STREAMING_SYSTEM_PROMPT,
    STREAMING_USER_PROMPT,
    format_conversation_history,
    format_party_positions_for_prompt,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt

logger = logging.getLogger(__name__)


class ConversationHandlerAgent:
    """
    Handles follow-up questions within a leaf conversation, and
    factual comparisons outside the exploration tree.

    The agent is driven exclusively through ``stream_from_llm``:
    the facade collects the streamed text and parses inline ``[id]``
    markers via ``extract_used_citations`` to rebuild the citation list.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "conversation_handler"

    def stream_from_llm(self, input: ConversationHandlerInput) -> AsyncIterator[str]:
        """
        Stream directly from LLM with party markers for frontend display.

        Uses streaming prompts that include ``[PARTY:id]`` section markers
        and inline ``[id]`` citations. Yields raw text chunks from the LLM.
        """
        messages = self._build_streaming_messages(input)
        return self._llm.stream(messages=messages, temperature=0.5)

    def _build_streaming_messages(self, input: ConversationHandlerInput) -> list:
        """Build messages for streaming LLM response with party markers."""
        knowledge = input.resolved_knowledge

        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        system_prompt = STREAMING_SYSTEM_PROMPT.format(party_context=party_context)

        subtopic_name = input.leaf_name or input.leaf_id
        subtopic_description = input.leaf_description or ""

        source_text = self._build_source_text(knowledge, input.parties_info)

        user_prompt = STREAMING_USER_PROMPT.format(
            subtopic_name=subtopic_name,
            subtopic_description=subtopic_description,
            message=input.message,
            conversation_history=format_conversation_history(
                input.conversation_history
            ),
            chunks=source_text,
        )

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    @staticmethod
    def _build_source_text(knowledge, parties_info) -> str:
        """Build source text from positions + RAG chunks (if available).

        Source IDs shown to the LLM are ``chunk.chunk_id`` so citations
        extracted from the response map directly back to the original
        chunks — including master position ids in study sessions.
        """
        # Start with extracted positions
        source = format_party_positions_for_prompt(
            knowledge.party_positions, parties_info
        )

        # Append RAG chunks if available (from on-demand retrieval)
        if knowledge.party_chunks:
            source += "\n\n== Zusätzliche Quelltexte aus den Wahlprogrammen ==\n"
            for party_id, chunks in knowledge.party_chunks.items():
                party_name = parties_info.get(
                    party_id,
                    type("P", (), {"name": party_id.upper()})(),
                ).name
                source += f"\n--- {party_name} ({party_id}) ---\n"
                for chunk in chunks[:5]:
                    source += f"[{chunk.chunk_id}] {chunk.content[:500]}\n\n"

        return source
