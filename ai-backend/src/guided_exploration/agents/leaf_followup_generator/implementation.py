# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Implementation of the leaf follow-up generator."""

import logging

from langchain_core.messages import HumanMessage

from src.guided_exploration.agents.leaf_followup_generator.interface import (
    LeafFollowUpInput,
    LeafFollowUpResult,
    TopicSwitchProposal,
)
from src.guided_exploration.agents.leaf_followup_generator.prompts import (
    LEAF_FOLLOWUP_PROMPT,
    LeafFollowUpLLMOutput,
)
from src.guided_exploration.agents.llm_provider import LLMProvider
from src.guided_exploration.models.content import (
    Analysis,
    SubtopicContent,
)
from src.guided_exploration.models.conversation import (
    Conversation,
    Message,
    MessageRole,
)

logger = logging.getLogger(__name__)


def _format_conversation(conversation: Conversation) -> str:
    """Format the leaf conversation as ``Nutzer: …`` / ``Assistent: …`` lines.

    Initial-content and analysis turns are expanded into their actual
    text (summary + per-party positions, or analysis sections) so the
    don't-repeat checks can compare against what the user has already
    seen — not just a placeholder.

    Past assistant turns also surface their persisted ``closure_ready``
    and ``topic_switch_proposal`` so the model can see what was already
    offered. If a prior turn had ``closure_ready=true`` and the user
    kept exploring (i.e. a later user message exists), the model should
    treat that as the user having declined closure and not re-offer it
    immediately.
    """
    if not conversation.messages:
        return "Keine Nachrichten."

    lines: list[str] = []
    for msg in conversation.messages:
        role = "Nutzer" if msg.role == MessageRole.USER else "Assistent"
        content = _stringify_message(msg)
        markers = _signal_markers(msg)
        if markers:
            lines.append(f"{role}: {content}\n  [{markers}]")
        else:
            lines.append(f"{role}: {content}")
    return "\n\n".join(lines)


def _stringify_message(msg: Message) -> str:
    if isinstance(msg.content, str):
        return msg.content
    if isinstance(msg.content, SubtopicContent):
        return _render_subtopic_content(msg.content)
    if isinstance(msg.content, Analysis):
        return _render_analysis(msg.content)
    return "[Strukturierter Inhalt — unbekannter Typ]"


def _render_subtopic_content(content: SubtopicContent) -> str:
    """Render the initial-content block as markdown the LLM can read."""
    parts: list[str] = ["[Initial-Content zum Leaf]"]
    if content.summary:
        parts.append(f"**Überblick:** {content.summary}")
    for position in content.party_positions:
        parts.append(f"**{position.party}:** {position.content}")
    if content.aspect_comparison and content.aspect_comparison.aspects:
        aspect_lines = ["**Aspekt-Vergleich:**"]
        for aspect in content.aspect_comparison.aspects:
            stances = "; ".join(
                f"{s.party}: {s.stance}" for s in aspect.party_stances
            )
            aspect_lines.append(f"- {aspect.name} — {stances}")
        parts.append("\n".join(aspect_lines))
    return "\n\n".join(parts)


def _render_analysis(analysis: Analysis) -> str:
    """Render an analysis turn as readable text."""
    parts: list[str] = ["[Analyse zum Leaf]"]
    if analysis.summary:
        parts.append(f"**Zusammenfassung:** {analysis.summary}")
    if analysis.context:
        parts.append(f"**Kontext:** {analysis.context}")
    if analysis.feasibility:
        parts.append(
            "**Umsetzbarkeit:**\n"
            + "\n".join(f"- {item}" for item in analysis.feasibility)
        )
    if analysis.considerations:
        parts.append(
            "**Weitere Punkte:**\n"
            + "\n".join(f"- {item}" for item in analysis.considerations)
        )
    return "\n\n".join(parts)


def _signal_markers(msg: Message) -> str:
    if msg.role != MessageRole.ASSISTANT:
        return ""
    parts: list[str] = []
    if msg.closure_ready:
        parts.append("closure-Einladung wurde gezeigt")
    if msg.topic_switch_proposal is not None:
        target_name = msg.topic_switch_proposal.target_node_name
        parts.append(f"topic-switch zu „{target_name}“ wurde angeboten")
    if msg.suggested_followups:
        chips = " | ".join(msg.suggested_followups)
        parts.append(f"chips: {chips}")
    return "; ".join(parts)


class LeafFollowUpGenerator:
    """Generates leaf-scoped follow-up chips + closure + topic-switch.

    Input includes the full leaf ``Conversation`` and the full available
    party-positions context, so the closure / switch flags can be judged
    against the leaf's real trajectory rather than a single q/r slice.
    """

    def __init__(self, llm_provider: LLMProvider):
        self._llm = llm_provider

    @property
    def name(self) -> str:
        return "leaf_followup_generator"

    async def generate(self, input: LeafFollowUpInput) -> LeafFollowUpResult:
        already_cited_text = (
            ", ".join(f"[{cid}]" for cid in input.already_cited_ids)
            if input.already_cited_ids
            else "keine"
        )
        neighboring_leaves_text = (
            input.neighboring_leaves
            or "(keine — kein Themenbaum-Kontext für diesen Aufruf verfügbar.)"
        )

        prompt = LEAF_FOLLOWUP_PROMPT.format(
            conversation=_format_conversation(input.conversation),
            available_context=input.available_context or "",
            already_cited_ids=already_cited_text,
            neighboring_leaves=neighboring_leaves_text,
        )

        try:
            llm_output: LeafFollowUpLLMOutput = (
                await self._llm.generate_structured(
                    messages=[HumanMessage(content=prompt)],
                    output_schema=LeafFollowUpLLMOutput,
                    temperature=0.5,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to generate leaf follow-up: {e}")
            return LeafFollowUpResult(
                questions=[], closure_ready=False, topic_switch_proposal=None
            )

        questions = llm_output.questions[:3]
        closure_ready = bool(llm_output.closure_ready)
        # closure_ready=true must come with empty questions per spec.
        if closure_ready and questions:
            logger.info(
                "Leaf follow-up: closure_ready=true with %d questions; "
                "dropping questions to honour closure spec",
                len(questions),
            )
            questions = []

        topic_switch_proposal: TopicSwitchProposal | None = None
        if llm_output.topic_switch_proposal is not None:
            proposal = llm_output.topic_switch_proposal
            valid = input.valid_neighbour_ids or {}
            target_id = proposal.target_node_id.strip()
            if target_id and target_id in valid:
                topic_switch_proposal = TopicSwitchProposal(
                    target_node_id=target_id,
                    target_node_name=valid[target_id],
                    reason=proposal.reason.strip(),
                )
            else:
                logger.info(
                    "Leaf follow-up: dropping topic_switch_proposal "
                    "with unknown target_node_id=%r (valid=%s)",
                    target_id,
                    sorted(valid.keys()),
                )

        return LeafFollowUpResult(
            questions=questions,
            closure_ready=closure_ready,
            topic_switch_proposal=topic_switch_proposal,
        )
