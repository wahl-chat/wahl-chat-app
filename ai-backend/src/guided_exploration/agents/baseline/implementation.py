# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Baseline streaming agent.

Produces a production-wahl.chat-shaped reply for the study's baseline
arm. Single public ``stream`` method — the agent has one job and one
prompt regime.
"""

from collections.abc import AsyncIterator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.guided_exploration.agents._shared import (
    BASE_RULES,
    BASELINE_APPLICATION_CONTEXT_CAPPED,
    BASELINE_APPLICATION_CONTEXT_UNCAPPED,
    EXPLORATION_GOALS,
)
from src.guided_exploration.agents.baseline.interface import BaselineInput
from src.guided_exploration.agents.baseline.prompts import (
    BASELINE_DARSTELLUNG_EXAMPLE_COMPACT,
    BASELINE_DARSTELLUNG_EXAMPLE_EXPANSIVE,
    BASELINE_LENGTH_DIRECTIVE_CAPPED,
    BASELINE_LENGTH_DIRECTIVE_UNCAPPED,
    BASELINE_SYSTEM_PROMPT,
    BASELINE_USER_PROMPT,
    CITATION_DIRECTIVE,
)
from src.guided_exploration.agents.llm_provider import LLMProvider


class BaselineAgent:
    """Streams baseline (production-wahl.chat-shaped) replies."""

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "baseline"

    def stream(self, input: BaselineInput) -> AsyncIterator[str]:
        """Stream a baseline reply."""
        messages = self._build_messages(input)
        system_prompt = str(messages[0].content)
        return self._llm.stream(messages=messages, temperature=0.3)

    def _build_messages(self, input: BaselineInput) -> list[BaseMessage]:
        history_text = (
            input.conversation_history
            if input.conversation_history
            else "Keine vorherigen Nachrichten."
        )

        if input.max_claims_per_party is not None:
            cap = input.max_claims_per_party
            claims_cap_directive = (
                "\n## WICHTIG — Antwortumfang (verpflichtend)\n"
                f"**Pro Partei höchstens {cap} Aussagen.** Diese Vorgabe gilt "
                "strikt für jede Antwort, unabhängig davon, wie viele "
                "Quellen oben gelistet sind.\n\n"
                f"- Auch wenn die Quellenliste mehr als {cap} Aussagen für "
                f"eine Partei enthält: nimm nur die {cap} relevantesten "
                "und lasse den Rest weg.\n"
                "- Wähle die Aussagen, die die Nutzerfrage am direktesten "
                "beantworten.\n"
                "- Lieber wenige, prägnante Stichpunkte als eine "
                "vollständige Liste.\n"
                "- Diese Obergrenze gilt **pro Antwort**, nicht über das "
                "ganze Gespräch hinweg — der Nutzer kann gezielt nach "
                "weiteren Aussagen fragen.\n\n"
                "❌ FALSCH: alle verfügbaren Aussagen einer Partei "
                "aufzählen.  \n"
                f"✅ RICHTIG: maximal {cap} Stichpunkte pro Partei-Karte, "
                "fokussiert auf die Frage.\n"
            )
            application_context = BASELINE_APPLICATION_CONTEXT_CAPPED
            darstellung_example = BASELINE_DARSTELLUNG_EXAMPLE_COMPACT
            length_directive = BASELINE_LENGTH_DIRECTIVE_CAPPED
        else:
            claims_cap_directive = ""
            application_context = BASELINE_APPLICATION_CONTEXT_UNCAPPED
            darstellung_example = BASELINE_DARSTELLUNG_EXAMPLE_EXPANSIVE
            length_directive = BASELINE_LENGTH_DIRECTIVE_UNCAPPED

        system_prompt = BASELINE_SYSTEM_PROMPT.format(
            exploration_goals=EXPLORATION_GOALS,
            application_context=application_context,
            context_name=input.context_name,
            conversation_history=history_text,
            parties_list=input.parties_list,
            rag_context=input.rag_context,
            claims_cap_directive=claims_cap_directive,
            darstellung_example=darstellung_example,
            length_directive=length_directive,
            citation_directive=CITATION_DIRECTIVE,
            base_rules=BASE_RULES,
        )

        user_prompt = BASELINE_USER_PROMPT.format(query=input.query)

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
