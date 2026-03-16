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
    format_party_positions_for_prompt,
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
    Generates structured content for a subtopic with streaming.

    Produces content structure:
    - Summary: Overview of the subtopic
    - Party positions: Each party's stance
    - Analysis (optional, generated on request)

    Streams content section by section with section markers
    for progressive UI rendering.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "content_generator"

    async def stream(self, input: ContentGeneratorInput) -> AsyncIterator[StreamChunk]:
        """
        Stream content generation for the subtopic.

        Yields chunks with section markers for UI rendering.
        Sections: summary, party_positions
        """
        # Generate full content first
        content = await self._generate_content(input)

        # Stream summary section
        async for chunk in self._stream_text(content.summary, "summary"):
            yield chunk

        # Stream party positions section
        positions_text = self._format_positions_for_streaming(content.party_positions)
        async for chunk in self._stream_text(positions_text, "party_positions"):
            yield chunk

        # Final chunk
        yield StreamChunk(content="", is_final=True, section=None)

    async def execute(self, input: ContentGeneratorInput) -> SubtopicContent:
        """
        Non-streaming execution returning complete content.

        Generates all content at once without streaming.
        """
        return await self._generate_content(input)

    async def _generate_content(self, input: ContentGeneratorInput) -> SubtopicContent:
        """Generate subtopic content using LLM."""
        knowledge = input.resolved_knowledge

        # Filter parties if specified
        parties = input.parties or list(knowledge.party_positions.keys())

        # Build party context for system prompt
        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        # Build system message
        system_prompt = SYSTEM_PROMPT.format(party_context=party_context)

        # Build user message with resolved knowledge
        user_prompt = GENERATION_PROMPT.format(
            subtopic_name=input.subtopic_name,
            path=" > ".join(input.path),
            party_positions=format_party_positions_for_prompt(
                knowledge.party_positions, input.parties_info
            ),
            citations=format_citations_pool(knowledge.citation_pool),
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Generate structured output
        llm_output: ContentGeneratorLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=ContentGeneratorLLMOutput,
            temperature=0.3,  # Low temperature for consistency
        )

        # Convert LLM output to domain model
        return self._convert_to_content(
            llm_output=llm_output,
            input=input,
            parties=parties,
        )

    def _convert_to_content(
        self,
        llm_output: ContentGeneratorLLMOutput,
        input: ContentGeneratorInput,
        parties: list[str],
    ) -> SubtopicContent:
        """Convert LLM output to SubtopicContent domain model."""
        knowledge = input.resolved_knowledge

        # Convert party positions
        party_positions = []
        for llm_pos in llm_output.party_positions:
            if llm_pos.party not in parties:
                continue

            party_positions.append(
                PartyPosition(
                    party=llm_pos.party,
                    content=llm_pos.content,
                )
            )

        return SubtopicContent(
            subtopic_id=input.subtopic_id,
            path=input.path,
            summary=llm_output.summary,
            party_positions=party_positions,
            analysis=None,  # Analysis generated on request
            citations=knowledge.citation_pool,
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
