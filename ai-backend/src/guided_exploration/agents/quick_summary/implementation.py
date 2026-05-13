# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Quick-summary streaming agent.

Single ``stream`` method producing a guided overview-or-cards reply.
The baseline reply path lives in ``BaselineAgent`` so each prompt
regime owns its own class.
"""

import logging
from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.guided_exploration.agents._shared import (
    BASE_RULES,
    EXPLORATION_GOALS,
    QUICK_SUMMARY_APPLICATION_CONTEXT,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.quick_summary.interface import QuickSummaryInput
from src.guided_exploration.agents.quick_summary.prompts import (
    CITATION_DIRECTIVE,
    GUIDED_FOCUS_DIRECTIVE,
    QUICK_SUMMARY_STREAMING_SYSTEM_PROMPT,
    QUICK_SUMMARY_STREAMING_USER_PROMPT,
)

logger = logging.getLogger(__name__)


class QuickSummaryAgent:
    """Streams guided quick-summary replies for the main chat surface."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "quick_summary"

    def stream(self, input: QuickSummaryInput) -> AsyncIterator[str]:
        """Stream a guided overview-or-cards reply."""
        messages = self._build_messages(input)
        system_prompt = str(messages[0].content)
        logger.info(
            "Quick summary path: GUIDED prompt | "
            "system_prompt_chars=%d | starts_with=%r",
            len(system_prompt),
            system_prompt[:120],
        )
        return self._llm.stream(messages=messages, temperature=0.3)

    def _build_messages(self, input: QuickSummaryInput) -> list[BaseMessage]:
        history_text = (
            input.conversation_history
            if input.conversation_history
            else "Keine vorherigen Nachrichten."
        )

        system_prompt = QUICK_SUMMARY_STREAMING_SYSTEM_PROMPT.format(
            exploration_goals=EXPLORATION_GOALS,
            application_context=QUICK_SUMMARY_APPLICATION_CONTEXT,
            context_name=input.context_name,
            conversation_history=history_text,
            parties_list=input.parties_list,
            rag_context=input.rag_context,
            focus_directive=GUIDED_FOCUS_DIRECTIVE,
            citation_directive=CITATION_DIRECTIVE,
            base_rules=BASE_RULES,
        )

        user_prompt = QUICK_SUMMARY_STREAMING_USER_PROMPT.format(
            query=input.query,
        )

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
