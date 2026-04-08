# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for topic scout agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.exploration import RetrievedChunk


class TopicDirection(BaseModel):
    """A subtopic direction that the user can choose to explore."""

    id: str = Field(..., description="Unique direction ID")
    name: str = Field(..., description="Short name for the direction")
    description: str = Field(
        ..., description="1-2 sentence description of this direction"
    )
    party_stances_preview: str = Field(
        ...,
        description="Brief summary of how the parties generally lean on this",
    )
    suggested_question: str = Field(
        ...,
        description="A concrete question the user could ask about this direction",
    )


class TopicScoutInput(BaseModel):
    """Input for topic scout agent."""

    query: str = Field(..., description="The user's original query")
    rag_chunks_text: str = Field(
        ..., description="Formatted RAG chunks from all parties"
    )
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Party information"
    )
    context_name: str = Field(
        default="", description="Election context name"
    )


class TopicScoutOutput(BaseModel):
    """Output from topic scout agent."""

    directions: list[TopicDirection] = Field(
        ..., description="3-5 topic directions the user can choose from"
    )
    cacheable: bool = Field(
        default=False,
        description="Whether this result can be cached for reuse",
    )
