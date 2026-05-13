# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of message classifier agent."""

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.message_classifier.interface import (
    MessageClassifierInput,
    MessageClassifierOutput,
)
from src.guided_exploration.agents.message_classifier.prompts import (
    MESSAGE_CLASSIFICATION_PROMPT,
    SYSTEM_PROMPT,
    format_conversation_context,
    format_last_assistant_block,
)


class MessageClassifierAgent(
    BaseAgent[MessageClassifierInput, MessageClassifierOutput]
):
    """
    Classifies user messages within an active exploration.

    Analyzes messages sent during an exploration to determine:
    - Intent (followup question, navigation command, analysis request, etc.)
    - Navigation target if applicable
    - Extracted question for followup intents

    This classification drives message handling:
    - FOLLOWUP_QUESTION: Route to LeafConversationHandlerAgent
    - NAVIGATION_COMMAND: Handle navigation in orchestrator
    - ANALYSIS_REQUEST: Route to AnalyzerAgent
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "message_classifier"

    async def execute(self, input: MessageClassifierInput) -> MessageClassifierOutput:
        """Classify the user message using LLM."""
        # Build system message with context
        system_prompt = SYSTEM_PROMPT.format(
            context_name=input.context_name,
        )

        # Format conversation context
        conversation_context = format_conversation_context(input.conversation_history)
        last_assistant_block = format_last_assistant_block(input.last_assistant_message)

        # Build user message
        user_prompt = MESSAGE_CLASSIFICATION_PROMPT.format(
            message=input.message,
            context_name=input.context_name,
            current_leaf_id=input.current_leaf_id or "Keins",
            last_assistant_block=last_assistant_block,
            conversation_context=conversation_context,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        return await self._llm.generate_structured(
            messages=messages,
            output_schema=MessageClassifierOutput,
            temperature=0.0,  # Deterministic for classification
        )
