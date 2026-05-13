# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for the main-chat follow-up chip generator."""

from pydantic import BaseModel, Field


class MainChatFollowUpInput(BaseModel):
    """Input for generating 3 fixed-slot quick replies after a main-chat reply.

    Used by both BaselineHandler and QuickSummaryHandler — same prompt,
    same shape, regardless of study condition.
    """

    query: str = Field(..., description="The user's last query")
    response: str = Field(..., description="The full assistant response just sent")
    available_context: str = Field(
        default="",
        description="Formatted RAG/party-positions context the response was grounded in",
    )
    topic_positions: str = Field(
        default="",
        description=(
            "Full position landscape for the current topic — grouped by party "
            "and subtopic. Used by the chip generator to pick a slot-1 "
            "follow-up that points at an aspect not yet covered. Empty for "
            "non-study contexts; the generator falls back to available_context."
        ),
    )
    conversation_history: str = Field(
        default="",
        description=(
            "Formatted prior conversation (last ~10 turns). Per-message "
            "truncation should be generous (~1500 chars) so the chip "
            "generator can see what was actually covered in earlier rich "
            "replies and avoid suggesting redundant follow-ups."
        ),
    )


class MainChatFollowUpResult(BaseModel):
    """Three fixed-slot quick replies for the main chat surface.

    Always exactly three entries: slot 1 = direct follow-up,
    slot 2 = clarification of a term, slot 3 = switch to a different
    campaign topic.
    """

    questions: list[str] = Field(
        default_factory=list,
        description="Exactly three quick-reply chips (slot 1/2/3).",
    )
