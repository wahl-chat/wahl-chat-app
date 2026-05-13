# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for the leaf follow-up generator."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.conversation import (
    Conversation,
    TopicSwitchProposal,
)

__all__ = [
    "LeafFollowUpInput",
    "LeafFollowUpResult",
    "TopicSwitchProposal",
]


class LeafFollowUpInput(BaseModel):
    """Input for generating leaf-scoped follow-up signals.

    The generator receives the FULL leaf conversation and FULL
    available knowledge, not just the last query/response slice — so
    the closure and topic-switch flags can be judged against the leaf's
    real trajectory.
    """

    conversation: Conversation = Field(
        ..., description="Full leaf conversation (all messages so far)"
    )
    available_context: str = Field(
        default="",
        description=(
            "Full available knowledge for the leaf — concatenated party "
            "positions / RAG context that the assistant could still cite."
        ),
    )
    already_cited_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Citation IDs already shown to the user across the leaf so "
            "far. Suggestions whose answer rests only on these IDs get "
            "filtered out by the prompt rule."
        ),
    )
    neighboring_leaves: str = Field(
        default="",
        description=(
            "Pre-formatted list of sibling leaves in the same tree as "
            "off-scope context — used to detect topic-switch candidates."
        ),
    )
    valid_neighbour_ids: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Map of neighbouring leaf ID → display name. The handler "
            "validates the LLM's proposed target_node_id against this "
            "map and drops the proposal silently if the ID is unknown."
        ),
    )


class LeafFollowUpResult(BaseModel):
    """Result of generate: chips plus closure / switch signals.

    All three signals only fire in the in-leaf flow.
    """

    questions: list[str] = Field(
        default_factory=list,
        description="0-2 short follow-up question chips.",
    )
    closure_ready: bool = Field(
        default=False,
        description="True iff the leaf is judged sufficiently explored.",
    )
    topic_switch_proposal: TopicSwitchProposal | None = Field(
        default=None,
        description=(
            "Set when the user's last question fits a sibling leaf "
            "better than the current one. Validated against "
            "valid_neighbour_ids in the implementation."
        ),
    )
