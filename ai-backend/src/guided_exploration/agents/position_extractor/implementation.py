# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of position extractor agent."""

import logging
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.position_extractor.interface import (
    PositionExtractorInput,
    PositionExtractorOutput,
)
from src.guided_exploration.agents.position_extractor.prompts import (
    EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
    PositionExtractorLLMOutput,
    format_chunks_for_party,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.position import Position, PartyPositions
from src.guided_exploration.models.content import Citation

logger = logging.getLogger(__name__)


class PositionExtractorAgent(BaseAgent[PositionExtractorInput, PositionExtractorOutput]):
    """
    Extracts concrete positions from a single party's documents.

    Unlike the old PartyTopicResolverAgent which extracted abstract topics,
    this agent extracts discrete, quotable statements — positions, demands,
    measures, targets, arguments, and criticisms.

    Each party is processed independently, allowing parallel execution.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "position_extractor"

    async def execute(self, input: PositionExtractorInput) -> PositionExtractorOutput:
        """
        Extract all concrete positions from a single party's documents.
        """
        # Format chunks for the prompt
        formatted_chunks = format_chunks_for_party(
            chunks=input.retrieved_chunks,
            party_id=input.party_id,
        )

        # Format party description if available
        party_desc = (
            f"- Beschreibung: {input.party_info.description}"
            if input.party_info.description
            else ""
        )

        # Build prompts
        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            party_id=input.party_id,
            party_name=input.party_info.name,
            party_long_name=input.party_info.long_name,
            party_description=party_desc,
        )

        user_prompt = EXTRACTION_PROMPT.format(
            query=input.query,
            retrieved_chunks=formatted_chunks,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Use structured output for reliable parsing
        llm_output: PositionExtractorLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=PositionExtractorLLMOutput,
            temperature=0.2,  # Low for factual extraction
        )

        # Convert LLM output to domain models
        positions = self._convert_to_positions(llm_output, input)

        party_positions = PartyPositions(
            party_id=input.party_id,
            positions=positions,
            relevance_to_query=llm_output.relevance_to_query,
        )

        logger.info(
            f"Extracted {len(positions)} positions from {input.party_info.name} "
            f"(relevance: {llm_output.relevance_to_query:.2f})"
        )

        return PositionExtractorOutput(
            party_id=input.party_id,
            party_positions=party_positions,
        )

    def _convert_to_positions(
        self,
        llm_output: PositionExtractorLLMOutput,
        input: PositionExtractorInput,
    ) -> list[Position]:
        """Convert LLM output to Position domain models with citations."""
        positions = []
        chunks = [c for c in input.retrieved_chunks if c.party_id == input.party_id]

        for llm_position in llm_output.positions:
            position_id = f"{input.party_id}-{uuid4().hex[:8]}"

            # Build citation from chunk metadata
            citation = None
            # chunk_index is 1-based from the prompt
            chunk_idx = llm_position.chunk_index - 1
            if 0 <= chunk_idx < len(chunks):
                chunk = chunks[chunk_idx]
                citation = Citation(
                    id=position_id,
                    party=input.party_id,
                    document=chunk.source_document,
                    section=chunk.source_section,
                    page=chunk.source_page,
                    source_document=chunk.source_document,
                )

            positions.append(
                Position(
                    id=position_id,
                    party_id=input.party_id,
                    content=llm_position.content,
                    quote=llm_position.quote,
                    position_type=llm_position.position_type,
                    citation=citation,
                    chunk_index=llm_position.chunk_index,
                )
            )

        return positions
