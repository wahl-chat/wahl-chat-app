# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of query classifier agent."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.query_classifier.interface import (
    QueryClassifierInput,
    QueryClassifierOutput,
)
from src.guided_exploration.agents.query_classifier.prompts import (
    CLASSIFICATION_PROMPT,
    SYSTEM_PROMPT,
    format_available_parties,
    format_conversation_context,
)

logger = logging.getLogger(__name__)


class QueryClassifierAgent(BaseAgent[QueryClassifierInput, QueryClassifierOutput]):
    """
    Classifies incoming user queries to determine routing.

    Analyzes user queries to determine:
    - Query type (factual simple, factual comparison, exploratory, clarification)
    - Detected parties mentioned in the query
    - Detected topics/themes
    - Whether clarification is needed

    This classification drives the system's response strategy:
    - FACTUAL_SIMPLE: Direct answer without exploration
    - FACTUAL_COMPARISON: Comparison answer without exploration
    - EXPLORATORY: Full guided exploration flow
    - CLARIFICATION: Ask clarifying questions first
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "query_classifier"

    async def execute(self, input: QueryClassifierInput) -> QueryClassifierOutput:
        """Classify the user query using LLM."""
        # Format dynamic content
        conversation_context = format_conversation_context(input.conversation_history)
        parties_formatted = format_available_parties(input.parties_info)

        # Build system message with context
        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
            available_parties=parties_formatted,
        )

        # Build user message
        user_prompt = CLASSIFICATION_PROMPT.format(
            query=input.query,
            context_id=input.context_id,
            context_name=input.context_name,
            conversation_context=conversation_context,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        # Use structured output for reliable parsing
        return await self._llm.generate_structured(
            messages=messages,
            output_schema=QueryClassifierOutput,
            temperature=0.0,  # Deterministic for classification
        )
