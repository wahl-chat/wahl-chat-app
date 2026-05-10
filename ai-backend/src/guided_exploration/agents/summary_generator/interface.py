# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for summary generator agent."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Citation, SubtopicContent
from src.guided_exploration.models.conversation import Conversation, LeafSummary
from src.guided_exploration.models.exploration import FinalSummary, SummaryTree


class LeafSummaryInput(BaseModel):
    """Input for generating a leaf conversation summary."""

    summary_type: Literal["leaf"] = "leaf"
    leaf_id: str = Field(..., description="ID of the leaf to summarize")
    leaf_name: str = Field(..., description="Display name of the leaf")
    conversation: Conversation = Field(..., description="The conversation to summarize")
    subtopic_content: SubtopicContent = Field(
        ..., description="The subtopic content discussed"
    )
    context_name: str = Field(..., description="Display name of the context")


class QuickSummaryInput(BaseModel):
    """Input for generating a quick summary without exploration."""

    summary_type: Literal["quick"] = "quick"
    query: str = Field(..., description="The original user query")
    rag_context: str = Field(
        ...,
        description="Formatted RAG context with document IDs for citation",
    )
    parties_list: str = Field(
        ...,
        description="Formatted list of relevant parties",
    )
    context_name: str = Field(..., description="Display name of the context")
    conversation_history: str = Field(
        default="",
        description=(
            "Formatted prior conversation (last ~10 turns) so the response "
            "can build on context, resolve back-references, and avoid "
            "repetition."
        ),
    )
    is_baseline: bool = Field(
        default=False,
        description=(
            "True if this summary is for a BASELINE study session. Switches "
            "the prompt to a regular-wahl.chat-style answer (no aspect-list "
            "Rückfrage on broad questions, claim-only citations) so the "
            "baseline doesn't bleed into exploration-style behaviour."
        ),
    )
    max_claims_per_party: int | None = Field(
        default=None,
        description=(
            "Optional cap on how many claims the baseline assistant may "
            "surface per party in this response. None = no cap (B groups). "
            "Set to 3 for the capped baseline arm (C groups). Only honoured "
            "when ``is_baseline`` is True."
        ),
    )


class QuickSummaryOutput(BaseModel):
    """Output from quick summary generation - direct text with inline citations."""

    text: str = Field(..., description="The full response text with inline citations")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations extracted from the response",
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the user",
    )


class TopicSwitchProposal(BaseModel):
    """A post-stream proposal that the user's question fits a sibling
    leaf better than the current one.

    Surfaced via ``SuggestedQuestionsResult.topic_switch_proposal`` and
    converted to a ``TopicSwitchSuggestedEvent`` by the followup handler.
    Only ever populated in the in-leaf flow.
    """

    target_node_id: str = Field(
        ..., description="ID of the sibling leaf the question fits better."
    )
    target_node_name: str = Field(
        ..., description="Display name of the target leaf."
    )
    reason: str = Field(
        ...,
        description=(
            "Short German message shown next to the switch action — "
            "why the other leaf fits better."
        ),
    )


class SuggestedQuestionsResult(BaseModel):
    """Result of generate_suggested_questions: chips plus closure / switch
    signals.

    ``closure_ready`` and ``topic_switch_proposal`` are only ever
    populated in the in-leaf flow. The followup handler forwards them
    to the frontend as a closure prompt and a topic-switch banner
    respectively. For other contexts (main_chat, baseline,
    factual_query) both stay empty.
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
            "better than the current one. Validated against the actual "
            "neighbouring leaf list in the followup handler."
        ),
    )


class FinalSummaryInput(BaseModel):
    """Input for generating final exploration summary."""

    summary_type: Literal["final"] = "final"
    exploration_id: str = Field(..., description="ID of the exploration")
    original_query: str = Field(
        ..., description="The original query that started the exploration"
    )
    summary_tree: SummaryTree = Field(..., description="The tree of leaf summaries")
    explored_subtopics: list[str] = Field(
        default_factory=list,
        description="List of explored subtopic IDs",
    )
    context_name: str = Field(..., description="Display name of the context")


# Union type for all summary inputs
SummaryInput = Annotated[
    Union[LeafSummaryInput, QuickSummaryInput, FinalSummaryInput],
    Field(discriminator="summary_type"),
]

# Union type for all summary outputs
SummaryOutput = Union[LeafSummary, QuickSummaryOutput, FinalSummary]
