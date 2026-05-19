# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of the exploration-overview agent."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.exploration_overview.interface import (
    ExplorationOverviewAgentInput,
)
from src.guided_exploration.agents.exploration_overview.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    ExplorationOverviewLLMOutput,
    format_areas_block,
    format_party_order,
    format_positions_block,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.models.exploration_overview import (
    ExplorationOverview,
    PartyStanceSummary,
)

logger = logging.getLogger(__name__)


class ExplorationOverviewAgent(
    BaseAgent[ExplorationOverviewAgentInput, ExplorationOverview]
):
    """Produces an intro paragraph and per-party stance summaries for the tree."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "exploration_overview"

    async def execute(
        self, input: ExplorationOverviewAgentInput
    ) -> ExplorationOverview:
        party_context = format_party_context_for_prompt(
            parties=input.parties,
            context_name=input.context_name,
        )

        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            party_context=party_context,
        )

        user_prompt = USER_PROMPT.format(
            query=input.query,
            areas_block=format_areas_block(input.areas, input.parties),
            positions_block=format_positions_block(
                input.positions_by_party, input.parties
            ),
            party_order=format_party_order(input.parties),
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: ExplorationOverviewLLMOutput = (
            await self._llm.generate_structured(
                messages=messages,
                output_schema=ExplorationOverviewLLMOutput,
                temperature=0.3,
            )
        )

        # Re-order party summaries to match the input order and drop any
        # parties the LLM hallucinated or dropped.
        by_party_id = {s.party_id: s.summary for s in llm_output.party_summaries}
        ordered: list[PartyStanceSummary] = []
        for party_id in input.parties.keys():
            summary = by_party_id.get(party_id)
            if summary:
                ordered.append(
                    PartyStanceSummary(party_id=party_id, summary=summary.strip())
                )

        return ExplorationOverview(
            intro_paragraph=llm_output.intro_paragraph.strip(),
            party_summaries=ordered,
        )
