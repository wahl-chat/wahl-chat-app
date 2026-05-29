# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Request/Response DTOs for guided exploration API."""

from typing import Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Request body for creating a new guided exploration session."""

    context_id: str = Field(
        default="bundestagswahl-2025",
        description="The election/political context ID",
    )
    user_id: str | None = Field(
        default=None,
        description="Firebase UID for authenticated users",
    )


class CreateSessionResponse(BaseModel):
    """Response when creating a new session."""

    session_id: str = Field(..., description="The created session ID")
    stream_url: str = Field(..., description="URL for SSE connection")
    context_id: str = Field(..., description="The context ID for this session")


class ResumeSessionResponse(BaseModel):
    """Response when resuming an existing session."""

    session_id: str = Field(..., description="The session ID")
    stream_url: str = Field(..., description="URL for SSE connection")
    context_id: str = Field(..., description="The context ID for this session")
    active_exploration: dict | None = Field(
        default=None,
        description="Active exploration state if any",
    )
    navigation_state: dict | None = Field(
        default=None,
        description="Current navigation state if in exploration",
    )
    messages: list[dict] = Field(
        default_factory=list,
        description="Session-level chat history",
    )
    explorations: list[dict] = Field(
        default_factory=list,
        description="All explorations in this session",
    )


class SendMessageRequest(BaseModel):
    """Request body for sending a message."""

    content: str = Field(
        ...,
        max_length=2000,
        description="The user's message content",
    )
    exploration_context: dict | None = Field(
        default=None,
        description="Context when message is within an exploration",
    )


class SubmitChoiceRequest(BaseModel):
    """Request body for submitting a user choice."""

    query_id: str = Field(..., description="ID of the query this choice responds to")
    choice: Literal["explore", "summary"] = Field(
        ...,
        description="User's choice: explore for deep dive, summary for quick answer",
    )


class NavigateRequest(BaseModel):
    """Request body for tree navigation."""

    target_path: list[str] = Field(
        ...,
        description="Path to navigate to, e.g., ['wohnen', 'mietpreisbremse']",
    )


class RequestAnalysisRequest(BaseModel):
    """Request body for requesting analysis on a leaf."""

    leaf_id: str = Field(..., description="ID of the leaf to analyze")


class MarkExploredRequest(BaseModel):
    """Request body for marking a leaf as explored."""

    leaf_id: str = Field(..., description="ID of the leaf to mark as explored")


class MarkClosedRequest(BaseModel):
    """Request body for recording a leaf-close event."""

    leaf_id: str = Field(..., description="ID of the leaf the user just closed")


class DirectionChoiceItem(BaseModel):
    """A single direction choice."""

    id: str = Field(..., description="Direction ID")
    name: str = Field(..., description="Direction name")


class SubmitDirectionChoiceRequest(BaseModel):
    """Request body for submitting topic direction choices (multi-select)."""

    query_id: str = Field(..., description="ID of the query this choice responds to")
    directions: list[DirectionChoiceItem] = Field(
        ..., description="Selected directions"
    )


