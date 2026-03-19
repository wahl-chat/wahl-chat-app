# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of content generator agent."""

import asyncio
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import StreamingAgent
from src.guided_exploration.agents.content_generator.interface import (
    ContentGeneratorInput,
)
from src.guided_exploration.agents.content_generator.prompts import (
    GENERATION_PROMPT,
    SYSTEM_PROMPT,
    ContentGeneratorLLMOutput,
    format_citations_pool,
    format_claims_for_content_prompt,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.models.content import (
    PartyPosition,
    SubtopicContent,
)
from src.guided_exploration.models.streaming import StreamChunk

logger = logging.getLogger(__name__)

# Streaming configuration
WORDS_PER_CHUNK = 5
CHUNK_DELAY = 0.05  # 50ms between chunks


class ContentGeneratorAgent(StreamingAgent[ContentGeneratorInput, SubtopicContent]):
    """
    Generates structured content for a leaf node from its claims.

    Produces:
    - Summary: Overview of the comparison point
    - Party positions: Each party's stance (from claims)
    - Suggested questions: Follow-up questions
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "content_generator"

    async def stream(self, input: ContentGeneratorInput) -> AsyncIterator[StreamChunk]:
        """Stream content generation for the leaf node."""
        content = await self._generate_content(input)

        async for chunk in self._stream_text(content.summary, "summary"):
            yield chunk

        positions_text = self._format_positions_for_streaming(content.party_positions)
        async for chunk in self._stream_text(positions_text, "party_positions"):
            yield chunk

        yield StreamChunk(content="", is_final=True, section=None)

    async def execute(self, input: ContentGeneratorInput) -> SubtopicContent:
        """Non-streaming execution returning complete content."""
        return await self._generate_content(input)

    async def _generate_content(self, input: ContentGeneratorInput) -> SubtopicContent:
        """Generate content from claims."""
        parties = input.parties or list(input.leaf_claims.keys())
        citations = list(input.leaf_citations) if input.leaf_citations else []

        # Collect citations from claims if not provided separately
        if not citations:
            for party_claims in input.leaf_claims.values():
                for claim in party_claims:
                    if claim.citation is not None:
                        citations.append(claim.citation)

        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        system_prompt = SYSTEM_PROMPT.format(party_context=party_context)

        user_prompt = GENERATION_PROMPT.format(
            subtopic_name=input.subtopic_name,
            path=" > ".join(input.path),
            party_positions=format_claims_for_content_prompt(
                input.leaf_claims, input.parties_info
            ),
            citations=format_citations_pool(citations),
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: ContentGeneratorLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=ContentGeneratorLLMOutput,
            temperature=0.3,
        )

        # Convert to domain model
        party_positions = [
            PartyPosition(party=pos.party, content=pos.content)
            for pos in llm_output.party_positions
            if pos.party in parties
        ]

        return SubtopicContent(
            subtopic_id=input.subtopic_id,
            path=input.path,
            summary=llm_output.summary,
            party_positions=party_positions,
            analysis=None,
            citations=citations,
            announcement=f"Inhalt zum Thema {input.subtopic_name} wird geladen.",
            suggested_questions=llm_output.suggested_questions,
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

    def _format_positions_for_streaming(self, positions: list[PartyPosition]) -> str:
        """Format party positions for streaming."""
        parts = []
        for pos in positions:
            parts.append(f"**{pos.party.upper()}**\n{pos.content}")
        return "\n\n".join(parts)
