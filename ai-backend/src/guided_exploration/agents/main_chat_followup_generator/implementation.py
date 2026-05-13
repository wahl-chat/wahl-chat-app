# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of the main-chat follow-up chip generator."""

import logging

from langchain_core.messages import HumanMessage

from src.guided_exploration.agents._shared import (
    EXPLORATION_GOALS,
    MAIN_CHAT_FOLLOWUP_APPLICATION_CONTEXT,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.main_chat_followup_generator.interface import (
    MainChatFollowUpInput,
    MainChatFollowUpResult,
)
from src.guided_exploration.agents.main_chat_followup_generator.prompts import (
    MAIN_CHAT_FOLLOWUP_PROMPT,
    MainChatFollowUpLLMOutput,
)

logger = logging.getLogger(__name__)


class MainChatFollowUpGenerator:
    """Generates 3 fixed-slot quick replies for the main chat surface.

    Same prompt for baseline and guided main-chat replies — keeps the
    chip experience identical across study conditions.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "main_chat_followup_generator"

    async def generate(
        self, input: MainChatFollowUpInput
    ) -> MainChatFollowUpResult:
        prompt = MAIN_CHAT_FOLLOWUP_PROMPT.format(
            exploration_goals=EXPLORATION_GOALS,
            application_context=MAIN_CHAT_FOLLOWUP_APPLICATION_CONTEXT,
            query=input.query,
            response=input.response,
            available_context=input.available_context or "",
            topic_positions=input.topic_positions or "(keine themenweiten Positionen geladen)",
            conversation_history=input.conversation_history or "",
        )

        try:
            llm_output: MainChatFollowUpLLMOutput = (
                await self._llm.generate_structured(
                    messages=[HumanMessage(content=prompt)],
                    output_schema=MainChatFollowUpLLMOutput,
                    temperature=0.5,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to generate main-chat follow-up chips: {e}")
            return MainChatFollowUpResult(questions=[])

        questions = llm_output.questions[:3]
        return MainChatFollowUpResult(questions=questions)
