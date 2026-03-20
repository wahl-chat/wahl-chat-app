# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of followup router agent."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.followup_router.interface import (
    FollowupRoute,
    FollowupRouterInput,
    FollowupRouterOutput,
)
from src.guided_exploration.agents.followup_router.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    FollowupRouterLLMOutput,
    format_claims_for_routing,
    format_other_leaves,
)
from src.guided_exploration.agents.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class FollowupRouterAgent(BaseAgent[FollowupRouterInput, FollowupRouterOutput]):
    """
    Fast routing agent that classifies follow-up questions.

    Decides whether a question can be answered from existing claims,
    needs additional RAG retrieval, belongs to another topic,
    or is completely off-topic.

    Uses FAST LLM tier for minimal latency (~200-400ms).
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "followup_router"

    async def execute(
        self, input: FollowupRouterInput
    ) -> FollowupRouterOutput:
        """Classify a follow-up question into a routing decision."""
        system_prompt = SYSTEM_PROMPT.format(
            leaf_name=input.leaf_name,
            leaf_description=input.leaf_description,
            existing_claims=input.existing_claims_summary,
            other_leaves=format_other_leaves(input.other_leaves),
        )

        user_prompt = USER_PROMPT.format(message=input.message)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: FollowupRouterLLMOutput = (
            await self._llm.generate_structured(
                messages=messages,
                output_schema=FollowupRouterLLMOutput,
                temperature=0.0,
            )
        )

        # Parse route with fallback
        try:
            route = FollowupRoute(llm_output.route)
        except ValueError:
            logger.warning(
                f"Unknown route '{llm_output.route}', falling back to ON_TOPIC_EXISTING"
            )
            route = FollowupRoute.ON_TOPIC_EXISTING

        logger.info(
            f"Routed follow-up to {route.value}"
            + (
                f" -> {llm_output.target_node_name}"
                if route == FollowupRoute.RELATED_TOPIC
                else ""
            )
        )

        return FollowupRouterOutput(
            route=route,
            target_node_id=llm_output.target_node_id,
            target_node_name=llm_output.target_node_name,
        )
