# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of summary generator agent."""

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from src.guided_exploration.agents.base import BaseAgent
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.agents.summary_generator.interface import (
    FinalSummaryInput,
    LeafSummaryInput,
    QuickSummaryInput,
    QuickSummaryOutput,
    SummaryInput,
    SummaryOutput,
)
from src.guided_exploration.agents.summary_generator.prompts import (
    BASELINE_QUICK_SUMMARY_SYSTEM_PROMPT,
    BASELINE_QUICK_SUMMARY_USER_PROMPT,
    BASELINE_SUGGESTED_QUESTIONS_PROMPT,
    CITATION_DIRECTIVE,
    FINAL_SUMMARY_PROMPT,
    GUIDED_FOCUS_DIRECTIVE,
    LEAF_SUMMARY_PROMPT,
    QUICK_SUMMARY_STREAMING_SYSTEM_PROMPT,
    QUICK_SUMMARY_STREAMING_USER_PROMPT,
    SUGGESTED_QUESTIONS_PROMPT_IN_LEAF,
    SUGGESTED_QUESTIONS_PROMPT_MAIN_CHAT,
    SYSTEM_PROMPT,
    FinalSummaryLLMOutput,
    LeafSummaryLLMOutput,
    SuggestedQuestionsLLMOutput,
    format_conversation_messages,
    format_explored_subtopics,
    format_leaf_summaries,
)
from src.guided_exploration.models.conversation import LeafSummary
from src.guided_exploration.models.exploration import FinalSummary

logger = logging.getLogger(__name__)


class SummaryGeneratorAgent(BaseAgent[SummaryInput, SummaryOutput]):
    """
    Generates summaries for different contexts.

    Handles three summary types:
    - Leaf summary: Summarizes a single leaf conversation
    - Quick summary: Provides a quick overview without exploration
    - Final summary: Summarizes the entire exploration session

    Uses the summary_type discriminator to route to the appropriate
    generation method.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "summary_generator"

    async def execute(self, input: SummaryInput) -> SummaryOutput:
        """
        Generate a summary based on input type.

        Routes to the appropriate generation method based on
        the summary_type discriminator.
        """
        if isinstance(input, LeafSummaryInput):
            return await self._generate_leaf_summary(input)
        elif isinstance(input, QuickSummaryInput):
            return await self._generate_quick_summary(input)
        elif isinstance(input, FinalSummaryInput):
            return await self._generate_final_summary(input)
        else:
            raise ValueError(f"Unknown summary input type: {type(input)}")

    def stream_quick_summary(self, input: QuickSummaryInput) -> AsyncIterator[str]:
        """
        Stream quick summary generation directly from LLM.

        Yields text chunks as they are generated.
        Use this for real-time streaming to the frontend.
        """
        messages = self._build_messages_for_input(input)
        return self._llm.stream(messages=messages, temperature=0.3)

    def _build_messages_for_input(
        self, input: QuickSummaryInput
    ) -> list[BaseMessage]:
        """Route to baseline or guided message builder based on session mode."""
        if input.is_baseline:
            messages = self._build_baseline_messages(input)
            system_prompt = str(messages[0].content)
            logger.info(
                "Quick summary path: BASELINE prompt | "
                "system_prompt_chars=%d | starts_with=%r | ends_with=%r",
                len(system_prompt),
                system_prompt[:120],
                system_prompt[-120:],
            )
            return messages
        messages = self._build_guided_messages(input)
        system_prompt = str(messages[0].content)
        logger.info(
            "Quick summary path: GUIDED prompt | "
            "system_prompt_chars=%d | starts_with=%r",
            len(system_prompt),
            system_prompt[:120],
        )
        return messages

    def _build_guided_messages(
        self, input: QuickSummaryInput
    ) -> list[BaseMessage]:
        """Build messages for the guided overview-or-cards quick summary."""
        history_text = (
            input.conversation_history
            if input.conversation_history
            else "Keine vorherigen Nachrichten."
        )

        system_prompt = QUICK_SUMMARY_STREAMING_SYSTEM_PROMPT.format(
            context_name=input.context_name,
            conversation_history=history_text,
            parties_list=input.parties_list,
            rag_context=input.rag_context,
            focus_directive=GUIDED_FOCUS_DIRECTIVE,
            citation_directive=CITATION_DIRECTIVE,
        )

        user_prompt = QUICK_SUMMARY_STREAMING_USER_PROMPT.format(
            query=input.query,
        )

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    def _build_baseline_messages(
        self, input: QuickSummaryInput
    ) -> list[BaseMessage]:
        """Build messages for the baseline (production-wahl.chat-shaped) reply.

        Fully separate from the guided template — no shared focus/citation
        directive swap. Mirrors `wahl_chat_response_system_prompt_template_str`
        + `get_wahl_chat_answer_guidelines` (src/prompts.py) so the contrast
        condition behaves like the regular wahl.chat assistant rather than
        an exploration variant with one swapped block.
        """
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
        else:
            claims_cap_directive = ""

        system_prompt = BASELINE_QUICK_SUMMARY_SYSTEM_PROMPT.format(
            context_name=input.context_name,
            conversation_history=history_text,
            parties_list=input.parties_list,
            rag_context=input.rag_context,
            claims_cap_directive=claims_cap_directive,
        )

        user_prompt = BASELINE_QUICK_SUMMARY_USER_PROMPT.format(
            query=input.query,
        )

        return [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

    async def _generate_leaf_summary(self, input: LeafSummaryInput) -> LeafSummary:
        """Generate a summary for a leaf conversation using LLM."""
        # Format conversation messages
        conversation_text = format_conversation_messages(input.conversation)

        # Build prompt
        prompt = LEAF_SUMMARY_PROMPT.format(
            context_name=input.context_name,
            leaf_name=input.leaf_name,
            subtopic_summary=input.subtopic_content.summary,
            conversation_messages=conversation_text,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Generate structured output
        llm_output: LeafSummaryLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=LeafSummaryLLMOutput,
            temperature=0.3,
        )

        logger.debug(f"Generated leaf summary for {input.leaf_id}")

        return LeafSummary(
            leaf_id=input.leaf_id,
            overview=llm_output.overview,
            key_points=llm_output.key_points,
            party_comparison=llm_output.party_comparison,
            generated_at=datetime.now(timezone.utc),
        )

    async def _generate_quick_summary(
        self, input: QuickSummaryInput
    ) -> QuickSummaryOutput:
        """Generate a quick summary (non-streaming, collects full response)."""
        messages = self._build_messages_for_input(input)

        # Generate direct text output (not structured)
        response_text = await self._llm.generate(
            messages=messages,
            temperature=0.3,
        )

        logger.debug(f"Generated quick summary for query: {input.query[:50]}...")

        return QuickSummaryOutput(
            text=response_text,
            citations=[],  # Citations are inline in the text
        )

    async def _generate_final_summary(self, input: FinalSummaryInput) -> FinalSummary:
        """Generate a final summary for the exploration using LLM."""
        # Format explored subtopics
        subtopics_text = format_explored_subtopics(input.explored_subtopics)

        # Format leaf summaries
        summaries_text = format_leaf_summaries(input.summary_tree)

        # Build prompt
        prompt = FINAL_SUMMARY_PROMPT.format(
            context_name=input.context_name,
            original_query=input.original_query,
            explored_subtopics=subtopics_text,
            leaf_summaries=summaries_text,
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ]

        # Generate structured output
        llm_output: FinalSummaryLLMOutput = await self._llm.generate_structured(
            messages=messages,
            output_schema=FinalSummaryLLMOutput,
            temperature=0.3,
        )

        logger.debug(f"Generated final summary for exploration {input.exploration_id}")

        return FinalSummary(
            closing_summary=llm_output.closing_summary,
            overview=llm_output.overview,
            key_findings=llm_output.key_findings,
            generated_at=datetime.now(timezone.utc),
        )

    async def generate_suggested_questions(
        self,
        query: str,
        response: str,
        available_context: str = "",
        conversation_history: str = "",
        context: str = "main_chat",
        is_baseline: bool = False,
        already_cited_ids: list[str] | None = None,
    ) -> list[str]:
        """Generate suggested follow-up questions based on full conversation context.

        ``is_baseline=True`` mirrors the production wahl.chat quick-reply
        prompt: three replies covering follow-up / clarification / topic
        switch.

        Otherwise the guided variants apply: ``context="in_leaf"`` invites
        neighboring sub-aspects of the same leaf; ``context="main_chat"``
        stays conservative and biases toward vertical drill-down.

        ``already_cited_ids`` lists the citation IDs that have already been
        shown to the user — suggestions whose answer would only rest on
        those IDs are filtered out by the prompt rule (only applied to the
        guided in-leaf / main-chat variants; the baseline prompt is left
        untouched to mirror production wahl.chat).
        """
        if is_baseline:
            template = BASELINE_SUGGESTED_QUESTIONS_PROMPT
            prompt = template.format(
                query=query,
                response=response,
                available_context=available_context or "",
                conversation_history=conversation_history or "",
            )
        else:
            template = (
                SUGGESTED_QUESTIONS_PROMPT_IN_LEAF
                if context == "in_leaf"
                else SUGGESTED_QUESTIONS_PROMPT_MAIN_CHAT
            )
            already_cited_text = (
                ", ".join(f"[{cid}]" for cid in already_cited_ids)
                if already_cited_ids
                else "keine"
            )
            prompt = template.format(
                query=query,
                response=response,
                available_context=available_context or "",
                conversation_history=conversation_history or "",
                already_cited_ids=already_cited_text,
            )

        messages = [
            HumanMessage(content=prompt),
        ]

        try:
            llm_output: SuggestedQuestionsLLMOutput = (
                await self._llm.generate_structured(
                    messages=messages,
                    output_schema=SuggestedQuestionsLLMOutput,
                    temperature=0.5,
                )
            )
            return llm_output.questions[:3]  # Limit to 3 questions
        except Exception as e:
            logger.warning(f"Failed to generate suggested questions: {e}")
            return []
