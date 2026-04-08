# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for query and message classification in guided exploration."""

from enum import Enum

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Type of user query for initial classification."""

    FACTUAL = "factual"
    EXPLORATORY = "exploratory"
    CLARIFICATION = "clarification"
    META = "meta"


class MessageIntent(str, Enum):
    """Intent of a message within an exploration."""

    FOLLOWUP_QUESTION = "followup_question"
    NAVIGATION_COMMAND = "navigation_command"
    ANALYSIS_REQUEST = "analysis_request"
    SUMMARY_REQUEST = "summary_request"
    UNCLEAR = "unclear"


class NavigationTarget(str, Enum):
    """Target for navigation commands."""

    NEXT = "next"
    PREVIOUS = "previous"
    BACK = "back"
    OVERVIEW = "overview"


class QueryClassificationInput(BaseModel):
    """Input for query classification."""

    query: str = Field(..., description="The user's query to classify")
    context_id: str = Field(..., description="The election/political context ID")
    conversation_history: list[str] | None = Field(
        default=None, description="Previous messages for context"
    )


class QueryClassificationOutput(BaseModel):
    """Output from query classification."""

    query_type: QueryType = Field(..., description="Classified type of the query")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the classification"
    )
    detected_parties: list[str] = Field(
        default_factory=list, description="Party IDs mentioned in the query"
    )
    needs_clarification: bool = Field(
        default=False, description="Whether clarification is needed"
    )
    clarification_question: str | None = Field(
        default=None, description="Question to ask for clarification"
    )


class MessageClassificationInput(BaseModel):
    """Input for message classification within an exploration."""

    message: str = Field(..., description="The user's message to classify")
    current_leaf_id: str | None = Field(
        default=None, description="Current leaf node ID if any"
    )
    has_exploration: bool = Field(
        default=False, description="Whether an exploration is active"
    )


class MessageClassificationOutput(BaseModel):
    """Output from message classification."""

    intent: MessageIntent = Field(..., description="Classified intent of the message")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the classification"
    )
    navigation_target: NavigationTarget | None = Field(
        default=None, description="Navigation target if intent is navigation"
    )
    extracted_question: str | None = Field(
        default=None, description="Extracted question for followup intents"
    )
