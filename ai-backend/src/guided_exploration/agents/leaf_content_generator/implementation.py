# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of leaf content generator agent."""

import asyncio
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents._shared import (
    BASE_RULES,
    CITATION_DIRECTIVE,
    EXPLORATION_GOALS,
    LEAF_CONTENT_APPLICATION_CONTEXT,
)
from src.guided_exploration.agents.base import StreamingAgent
from src.guided_exploration.agents.leaf_content_generator.interface import (
    LeafContentGeneratorInput,
)
from src.guided_exploration.agents.leaf_content_generator.prompts import (
    GENERATION_PROMPT,
    SYSTEM_PROMPT,
    LeafContentGeneratorLLMOutput,
    format_citations_pool,
    format_positions_for_content_prompt,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.models.content import (
    AspectComparison,
    ComparisonAspect,
    PartyPosition,
    PartyStance,
    SubtopicContent,
)
from src.guided_exploration.models.streaming import StreamChunk

logger = logging.getLogger(__name__)

# Streaming configuration
WORDS_PER_CHUNK = 5
CHUNK_DELAY = 0.05  # 50ms between chunks


class LeafContentGeneratorAgent(
    StreamingAgent[LeafContentGeneratorInput, SubtopicContent]
):
    """
    Generates structured content for a leaf node from its positions.

    Produces:
    - Summary: Overview of the comparison point
    - Party positions: Each party's stance (from positions)
    - Suggested questions: Follow-up questions
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        fast_llm_provider: LLMProvider | None = None,
    ):
        self._llm = llm_provider
        self._fast_llm = fast_llm_provider or llm_provider

    @property
    def name(self) -> str:
        return "leaf_content_generator"

    async def stream(
        self, input: LeafContentGeneratorInput
    ) -> AsyncIterator[StreamChunk]:
        """Stream content generation for the leaf node."""
        content = await self._generate_content(input)

        async for chunk in self._stream_text(content.summary, "summary"):
            yield chunk

        positions_text = self._format_positions_for_streaming(content.party_positions)
        async for chunk in self._stream_text(positions_text, "party_positions"):
            yield chunk

        yield StreamChunk(content="", is_final=True, section=None)

    async def execute(self, input: LeafContentGeneratorInput) -> SubtopicContent:
        """Non-streaming execution returning complete content."""
        return await self._generate_content(input)

    async def _generate_content(
        self, input: LeafContentGeneratorInput
    ) -> SubtopicContent:
        """Generate content from positions."""
        parties = input.parties or list(input.leaf_positions.keys())
        citations = list(input.leaf_citations) if input.leaf_citations else []

        # Collect citations from positions if not provided separately
        if not citations:
            for party_positions in input.leaf_positions.values():
                for position in party_positions:
                    if position.citation is not None:
                        citations.append(position.citation)

        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        system_prompt = SYSTEM_PROMPT.format(
            exploration_goals=EXPLORATION_GOALS,
            application_context=LEAF_CONTENT_APPLICATION_CONTEXT,
            party_context=party_context,
            citation_directive=CITATION_DIRECTIVE,
            base_rules=BASE_RULES,
        )

        user_prompt = GENERATION_PROMPT.format(
            subtopic_name=input.subtopic_name,
            path=" > ".join(input.path),
            party_positions=format_positions_for_content_prompt(
                input.leaf_positions, input.parties_info
            ),
            citations=format_citations_pool(citations),
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: LeafContentGeneratorLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=LeafContentGeneratorLLMOutput,
            temperature=0.3,
        )

        # Convert to domain model
        party_positions = [
            PartyPosition(party=pos.party, content=pos.content)
            for pos in llm_output.party_positions
            if pos.party in parties
        ]

        # Extract aspect comparison if 2+ parties
        aspect_comparison = None
        if len(party_positions) >= 2:
            try:
                aspect_comparison = await self._extract_aspects(
                    input.subtopic_name, party_positions
                )
            except Exception:
                logger.warning(
                    f"Failed to extract aspects for {input.subtopic_id}",
                    exc_info=True,
                )

        return SubtopicContent(
            subtopic_id=input.subtopic_id,
            path=input.path,
            summary=llm_output.summary,
            party_positions=party_positions,
            analysis=None,
            aspect_comparison=aspect_comparison,
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

    async def _extract_aspects(
        self,
        subtopic_name: str,
        party_positions: list[PartyPosition],
    ) -> AspectComparison | None:
        """Extract comparable aspects from party positions using FAST LLM."""
        positions_text = "\n\n".join(
            f"**{pos.party}**: {pos.content}" for pos in party_positions
        )

        from pydantic import BaseModel, Field

        class LLMPartyStance(BaseModel):
            party: str = Field(..., description="Parteiname")
            stance: str = Field(
                ..., description="Kurze Beschreibung der Position (max 1-2 Sätze)"
            )

        class LLMComparisonAspect(BaseModel):
            name: str = Field(..., description="Name des Aspekts")
            party_stances: list[LLMPartyStance] = Field(
                ..., description="Position jeder Partei zu diesem Aspekt"
            )

        class LLMAspectOutput(BaseModel):
            aspects: list[LLMComparisonAspect] = Field(
                ..., description="3-6 vergleichbare Aspekte"
            )

        messages = [
            SystemMessage(
                content=(
                    "Du extrahierst vergleichbare Aspekte aus Parteipositionen. "
                    "Identifiziere 3-6 konkrete Aspekte zu denen sich die Parteien "
                    "positionieren. Für jeden Aspekt: kurze Beschreibung der Position "
                    "jeder Partei (max 1-2 Sätze). Nur Deutsch."
                )
            ),
            HumanMessage(
                content=(
                    f"Thema: {subtopic_name}\n\n"
                    f"Parteipositionen:\n{positions_text}\n\n"
                    "Extrahiere vergleichbare Aspekte."
                )
            ),
        ]

        llm_output: LLMAspectOutput = await self._fast_llm.generate_structured(
            messages=messages,
            output_schema=LLMAspectOutput,
            temperature=0.2,
        )

        if not llm_output.aspects:
            return None

        return AspectComparison(
            aspects=[
                ComparisonAspect(
                    name=a.name,
                    party_stances=[
                        PartyStance(party=s.party, stance=s.stance)
                        for s in a.party_stances
                    ],
                )
                for a in llm_output.aspects
            ]
        )

    def _format_positions_for_streaming(self, positions: list[PartyPosition]) -> str:
        """Format party positions for streaming."""
        parts = []
        for pos in positions:
            parts.append(f"**{pos.party.upper()}**\n{pos.content}")
        return "\n\n".join(parts)
