# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of topic scout agent."""

import logging
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.party_context import format_party_context_for_prompt
from src.guided_exploration.agents.topic_scout.interface import (
    TopicDirection,
    TopicScoutInput,
    TopicScoutOutput,
)
from src.guided_exploration.agents.topic_scout.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT,
    TopicScoutLLMOutput,
)
from src.guided_exploration.agents.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class TopicScoutAgent(BaseAgent[TopicScoutInput, TopicScoutOutput]):
    """
    Fast agent that identifies major subtopic directions from RAG chunks.

    Given a user query and retrieved chunks, extracts 3-5 concrete
    topic directions with brief party stance previews. Uses FAST LLM
    tier for minimal latency.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "topic_scout"

    async def execute(self, input: TopicScoutInput) -> TopicScoutOutput:
        """Identify topic directions from RAG chunks."""
        party_context = format_party_context_for_prompt(
            parties=input.parties_info,
            context_name=input.context_name,
        )

        system_prompt = SYSTEM_PROMPT.format(party_context=party_context)
        user_prompt = USER_PROMPT.format(
            query=input.query,
            rag_chunks=input.rag_chunks_text,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        llm_output: TopicScoutLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=TopicScoutLLMOutput,
            temperature=0.3,
        )

        directions = [
            TopicDirection(
                id=uuid4().hex[:8],
                name=d.name,
                description=d.description,
                party_stances_preview=d.party_stances_preview,
                suggested_question=d.suggested_question,
            )
            for d in llm_output.directions
        ]

        logger.info(
            f"Scouted {len(directions)} topic directions for query: "
            f"{input.query[:50]} (cacheable={llm_output.cacheable})"
        )

        return TopicScoutOutput(
            directions=directions,
            cacheable=llm_output.cacheable,
        )
