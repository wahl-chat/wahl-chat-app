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
