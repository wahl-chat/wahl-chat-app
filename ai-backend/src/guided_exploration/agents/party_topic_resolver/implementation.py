# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of party topic resolver agent."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.party_topic_resolver.interface import (
    PartyTopicResolverInput,
    PartyTopicResolverOutput,
)
from src.guided_exploration.agents.party_topic_resolver.prompts import (
    RESOLUTION_PROMPT,
    SYSTEM_PROMPT,
    PartyTopicsLLMOutput,
    format_chunks_for_party,
)
from src.guided_exploration.models.exploration import (
    PartySubtopic,
    PartyTopic,
    PartyTopicTree,
)

logger = logging.getLogger(__name__)


class PartyTopicResolverAgent(
    BaseAgent[PartyTopicResolverInput, PartyTopicResolverOutput]
):
    """
    Resolves topics from a single party's documents.

    Analyzes retrieved chunks for one party to extract:
    - Topics relevant to the user's query
    - Subtopics within each topic
    - Importance scores for each topic
    - Content availability flags

    Each party is processed independently, allowing parallel execution.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "party_topic_resolver"

    async def execute(self, input: PartyTopicResolverInput) -> PartyTopicResolverOutput:
        """
        Resolve topics from a single party's documents using LLM.

        Analyzes retrieved chunks to extract topics, subtopics, and importance scores.
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

        # Build system prompt with context and party info
        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            party_id=input.party_id,
            party_name=input.party_info.name,
            party_long_name=input.party_info.long_name,
            party_description=party_desc,
        )

        # Build user prompt
        user_prompt = RESOLUTION_PROMPT.format(
            query=input.query,
            retrieved_chunks=formatted_chunks,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Use structured output for reliable parsing
        llm_output: PartyTopicsLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=PartyTopicsLLMOutput,
            temperature=0.3,  # Slightly creative for topic extraction
        )

        # Convert LLM output to domain models
        topics = self._convert_to_party_topics(llm_output, input.party_id)

        party_tree = PartyTopicTree(
            party_id=input.party_id,
            topics=topics,
            relevance_to_query=llm_output.relevance_to_query,
        )

        return PartyTopicResolverOutput(
            party_id=input.party_id,
            party_topic_tree=party_tree,
        )

    def _convert_to_party_topics(
        self,
        llm_output: PartyTopicsLLMOutput,
        party_id: str,
    ) -> list[PartyTopic]:
        """Convert LLM output to PartyTopic domain models."""
        topics = []

        for llm_topic in llm_output.topics:
            subtopics = [
                PartySubtopic(
                    id=f"{llm_topic.id}.{llm_subtopic.id}",
                    name=llm_subtopic.name,
                    description=llm_subtopic.description,
                    has_content=llm_subtopic.has_content,
                )
                for llm_subtopic in llm_topic.subtopics
            ]

            topics.append(
                PartyTopic(
                    id=llm_topic.id,
                    name=llm_topic.name,
                    description=llm_topic.description,
                    subtopics=subtopics,
                    importance_score=llm_topic.importance_score,
                )
            )

        return topics
