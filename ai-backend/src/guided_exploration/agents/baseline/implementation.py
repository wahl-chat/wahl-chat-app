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
            claims_cap_directive = (
                "\n## WICHTIG — Antwortzuschnitt (verpflichtend)\n"
                "**Eine Antwort = ein Sub-Aspekt.** Dieser Modus zerlegt "
                "das Thema in kleine, gut verdauliche Schritte. Du machst "
                "nicht alles auf einmal auf, sondern führst die Nutzer:in "
                "Schritt für Schritt.\n\n"
                "1. **Wähle EINEN Sub-Aspekt**, der die Nutzerfrage am "
                "direktesten beantwortet (z.B. „CO2-Preis", „Klimageld", "
                "„Verbrenner-Aus" — nicht „Klimapolitik" als Ganzes).\n"
                "2. **Zeige die Positionen der Parteien zu genau diesem "
                "einen Sub-Aspekt** — konzentriert, ohne Material zu "
                "anderen Aspekten des Themas einzustreuen. Pro Partei "
                "reichen 1–2 prägnante Aussagen zum gewählten "
                "Sub-Aspekt; mehr verwässert den Fokus.\n"
                "3. **Schließe mit einer kurzen Zeile**, die 2–3 andere "
                "Sub-Aspekte des Themas als Angebot nennt — die "
                "Nutzer:in wählt, welcher als nächstes drankommt.\n\n"
                "Wenn die Frage selbst schon eng auf einen Sub-Aspekt "
                "zielt, beantworte sie direkt und schlage als nächstes "
                "2–3 benachbarte Aspekte vor.\n\n"
                "❌ FALSCH: das gesamte Thema in einer Antwort "
                "auffächern, auch wenn jede Partei nur kurze Stichpunkte "
                "bekommt.  \n"
                "✅ RICHTIG: ein Sub-Aspekt vollständig behandelt, die "
                "anderen als Angebot in einer Zeile.\n"
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
