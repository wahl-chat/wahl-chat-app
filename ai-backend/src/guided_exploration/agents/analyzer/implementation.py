# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of analyzer agent."""

import asyncio
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.analyzer.interface import AnalyzerInput
from src.guided_exploration.agents.analyzer.prompts import (
    ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    AnalysisLLMOutput,
    format_focus_areas,
    format_party_positions_for_analysis,
)
from src.guided_exploration.agents.base import StreamingAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.content import Analysis
from src.guided_exploration.models.streaming import StreamChunk

logger = logging.getLogger(__name__)

# Streaming configuration
WORDS_PER_CHUNK = 5
CHUNK_DELAY = 0.05  # 50ms between chunks


class AnalyzerAgent(StreamingAgent[AnalyzerInput, Analysis]):
    """
    Generates critical analysis for a subtopic with streaming.

    Produces structured analysis with:
    - Summary: Overall assessment
    - Context: Background and current situation
    - Feasibility: Practical implementation considerations
    - Considerations: Additional points to consider

    Streams content section by section for progressive rendering.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "analyzer"

    async def stream(self, input: AnalyzerInput) -> AsyncIterator[StreamChunk]:
        """
        Stream analysis generation for the subtopic.

        Yields chunks with section markers: summary, context, feasibility, considerations.
        """
        # Generate full analysis via LLM
        analysis = await self._generate_analysis(input)

        # Stream summary section
        async for chunk in self._stream_text(analysis.summary, "summary"):
            yield chunk

        # Stream context section
        async for chunk in self._stream_text(analysis.context, "context"):
            yield chunk

        # Stream feasibility section (combined as text with bullet points)
        feasibility_text = "\n".join(f"• {point}" for point in analysis.feasibility)
        async for chunk in self._stream_text(feasibility_text, "feasibility"):
            yield chunk

        # Stream considerations section
        considerations_text = "\n".join(
            f"• {point}" for point in analysis.considerations
        )
        async for chunk in self._stream_text(considerations_text, "considerations"):
            yield chunk

        # Final chunk
        yield StreamChunk(content="", is_final=True, section=None)

    async def execute(self, input: AnalyzerInput) -> Analysis:
        """
        Non-streaming execution returning complete analysis.
        """
        return await self._generate_analysis(input)

    async def _generate_analysis(self, input: AnalyzerInput) -> Analysis:
        """Generate analysis using the LLM."""
        # Format party positions
        party_positions = format_party_positions_for_analysis(
            input.resolved_knowledge.party_positions,
            input.parties_info,
        )

        # Format focus areas
        focus_instruction = format_focus_areas(input.focus_areas)

        # Build prompt
        prompt = ANALYSIS_PROMPT.format(
            context_name=input.context_name,
            leaf_name=input.leaf_name,
            subtopic_summary=input.subtopic_content.summary,
            party_positions=party_positions,
            focus_instruction=focus_instruction,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Generate structured output
        llm_output: AnalysisLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=AnalysisLLMOutput,
            temperature=0.3,
        )

        logger.debug(f"Generated analysis for {input.leaf_id}")

        return Analysis(
            summary=llm_output.summary,
            context=llm_output.context,
            feasibility=llm_output.feasibility,
            considerations=llm_output.considerations,
            sources=llm_output.sources,
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
