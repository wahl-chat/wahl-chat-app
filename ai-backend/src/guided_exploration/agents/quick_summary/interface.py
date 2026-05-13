# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for quick-summary streaming agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Citation


class QuickSummaryInput(BaseModel):
    """Input for streaming a guided quick summary."""

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


class QuickSummaryOutput(BaseModel):
    """Output collected from a streamed quick summary."""

    text: str = Field(..., description="The full response text with inline citations")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations extracted from the response",
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for the user",
    )
