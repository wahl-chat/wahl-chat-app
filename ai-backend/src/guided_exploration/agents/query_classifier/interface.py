# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for query classifier agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.classification import QueryType


class QueryClassifierInput(BaseModel):
    """Input for query classification."""

    query: str = Field(..., description="The user's query to classify")
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(
        ...,
        description="Human-readable name of the context (e.g., 'Bundestagswahl 2025', 'Kommunalwahl Hamburg')",
    )
    parties_info: dict[str, PartyInfo] = Field(
        ...,
        description="Available parties for the context: {party_id: PartyInfo}",
    )
    conversation_history: list[str] = Field(
        default_factory=list,
        description="Previous messages for context",
    )


class QueryClassifierOutput(BaseModel):
    """Output from query classification."""

    query_type: QueryType = Field(..., description="Classified type of the query")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the classification"
    )
    detected_parties: list[str] = Field(
        default_factory=list,
        description="Party IDs mentioned in the query",
    )
    rag_query: str = Field(
        ...,
        description="Optimized query for RAG retrieval (keywords, no filler words)",
    )
    needs_clarification: bool = Field(
        default=False,
        description="Whether clarification is needed",
    )
    clarification_question: str | None = Field(
        default=None,
        description="Question to ask for clarification",
    )
