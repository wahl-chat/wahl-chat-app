# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of analyzer agent."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.analyzer.interface import AnalyzerInput
from src.guided_exploration.agents.analyzer.prompts import (
    ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    AnalysisLLMOutput,
    format_focus_areas,
    format_party_positions_for_analysis,
)
from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.content import Analysis

logger = logging.getLogger(__name__)


class AnalyzerAgent(BaseAgent[AnalyzerInput, Analysis]):
    """
    Generates structured critical analysis for a subtopic.

    Produces an Analysis with summary, context, feasibility, and considerations.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "analyzer"

    async def execute(self, input: AnalyzerInput) -> Analysis:
        return await self._generate_analysis(input)

    async def _generate_analysis(self, input: AnalyzerInput) -> Analysis:
        """Generate analysis using the LLM."""
        party_positions = format_party_positions_for_analysis(
            input.resolved_knowledge.party_positions,
            input.parties_info,
        )

        focus_instruction = format_focus_areas(input.focus_areas)

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
