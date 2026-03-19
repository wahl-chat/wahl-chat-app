# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of claim extractor agent."""

import logging
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.claim_extractor.interface import (
    ClaimExtractorInput,
    ClaimExtractorOutput,
)
from src.guided_exploration.agents.claim_extractor.prompts import (
    EXTRACTION_PROMPT,
    SYSTEM_PROMPT,
    ClaimExtractorLLMOutput,
    format_chunks_for_party,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.claim import Claim, PartyClaims
from src.guided_exploration.models.content import Citation

logger = logging.getLogger(__name__)


class ClaimExtractorAgent(BaseAgent[ClaimExtractorInput, ClaimExtractorOutput]):
    """
    Extracts concrete claims from a single party's documents.

    Unlike the old PartyTopicResolverAgent which extracted abstract topics,
    this agent extracts discrete, quotable statements — positions, demands,
    measures, targets, arguments, and criticisms.

    Each party is processed independently, allowing parallel execution.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "claim_extractor"

    async def execute(self, input: ClaimExtractorInput) -> ClaimExtractorOutput:
        """
        Extract all concrete claims from a single party's documents.
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
        llm_output: ClaimExtractorLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=ClaimExtractorLLMOutput,
            temperature=0.2,  # Low for factual extraction
        )

        # Convert LLM output to domain models
        claims = self._convert_to_claims(llm_output, input)

        party_claims = PartyClaims(
            party_id=input.party_id,
            claims=claims,
            relevance_to_query=llm_output.relevance_to_query,
        )

        logger.info(
            f"Extracted {len(claims)} claims from {input.party_info.name} "
            f"(relevance: {llm_output.relevance_to_query:.2f})"
        )

        return ClaimExtractorOutput(
            party_id=input.party_id,
            party_claims=party_claims,
        )

    def _convert_to_claims(
        self,
        llm_output: ClaimExtractorLLMOutput,
        input: ClaimExtractorInput,
    ) -> list[Claim]:
        """Convert LLM output to Claim domain models with citations."""
        claims = []
        chunks = [c for c in input.retrieved_chunks if c.party_id == input.party_id]

        for llm_claim in llm_output.claims:
            claim_id = f"{input.party_id}-{uuid4().hex[:8]}"

            # Build citation from chunk metadata
            citation = None
            # chunk_index is 1-based from the prompt
            chunk_idx = llm_claim.chunk_index - 1
            if 0 <= chunk_idx < len(chunks):
                chunk = chunks[chunk_idx]
                citation = Citation(
                    id=claim_id,
                    party=input.party_id,
                    document=chunk.source_document,
                    section=chunk.source_section,
                    page=chunk.source_page,
                    source_document=chunk.source_document,
                )

            claims.append(
                Claim(
                    id=claim_id,
                    party_id=input.party_id,
                    content=llm_claim.content,
                    quote=llm_claim.quote,
                    claim_type=llm_claim.claim_type,
                    citation=citation,
                    chunk_index=llm_claim.chunk_index,
                )
            )

        return claims
