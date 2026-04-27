# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for session management in guided exploration."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.exploration import Exploration
from src.guided_exploration.models.navigation import NavigationState


class SessionMessageType(str, Enum):
    """Type of message in session-level chat."""

    USER = "user"
    ASSISTANT = "assistant"
    EXPLORATION_START = "exploration_start"  # Reference to exploration
    TOPIC_DIRECTIONS = "topic_directions"  # Topic direction choices
    # Research-only audit messages: persisted so the study admin can see
    # what the participant was offered and what they picked. The chat
    # frontend filters these out — they are not user-facing turns.
    CHOICE_PROMPT = "choice_prompt"  # System offered explore/summary choice
    CHOICE_MADE = "choice_made"  # User picked explore or summary


class SessionMessage(BaseModel):
    """A message in the session-level chat history."""

    id: str = Field(..., description="Unique message identifier")
    type: SessionMessageType = Field(..., description="Type of message")
    content: str | None = Field(
        default=None, description="Message content (None for exploration_start)"
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations for this message (for quick summaries)",
    )
    exploration_id: str | None = Field(
        default=None, description="Set for exploration_start type"
    )
    exploration_query: str | None = Field(
        default=None, description="Original query for exploration"
    )
    directions: list[dict] | None = Field(
        default=None,
        description="Topic direction choices (for topic_directions type)",
    )
    directions_query_id: str | None = Field(
        default=None,
        description="Query ID for direction choice tracking",
    )
    selected_directions: list[str] | None = Field(
        default=None,
        description="Names of directions the user selected (set on topic_directions message after submission)",
    )
    query_id: str | None = Field(
        default=None,
        description="Pending-query ID linking choice_prompt and choice_made messages.",
    )
    options: list[dict] | None = Field(
        default=None,
        description="Options offered (for choice_prompt type).",
    )
    choice: Literal["explore", "summary"] | None = Field(
        default=None,
        description="Option the user picked (for choice_made type).",
    )
    original_query: str | None = Field(
        default=None,
        description="Original user query the choice was about (for choice_prompt/choice_made).",
    )
    timestamp: datetime = Field(..., description="When the message was created")


class SessionMode(str, Enum):
    """Mode of the session - affects available features."""

    GUIDED = "guided"  # Full exploration with topic tree
    BASELINE = "baseline"  # Summary-only, no exploration choice


class Session(BaseModel):
    """Session stored in Firebase."""

    id: str = Field(..., description="Unique session identifier")
    context_id: str = Field(
        ...,
        description="The election/political context ID, e.g., 'bundestagswahl-2025'",
    )
    user_id: str | None = Field(
        default=None, description="Firebase UID, null for anonymous users"
    )
    mode: SessionMode = Field(
        default=SessionMode.GUIDED,
        description="Session mode - guided allows exploration, baseline is summary-only",
    )
    created_at: datetime = Field(..., description="When the session was created")
    last_active_at: datetime = Field(
        ..., description="When the session was last active"
    )
    preferences: dict = Field(
        default_factory=dict, description="User preferences for this session"
    )
    messages: list[SessionMessage] = Field(
        default_factory=list, description="Session-level chat messages"
    )


class SessionInfo(BaseModel):
    """Response when creating/resuming session."""

    session_id: str = Field(..., description="The session ID")
    stream_url: str = Field(..., description="URL for SSE connection")
    active_exploration: Exploration | None = Field(
        default=None, description="Currently active exploration if any"
    )


class ExplorationContext(BaseModel):
    """Context passed with messages when in exploration."""

    exploration_id: str = Field(..., description="ID of the current exploration")
    leaf_id: str | None = Field(
        default=None, description="Current leaf node ID if navigated to one"
    )


class ExportOptions(BaseModel):
    """Options for PDF export."""

    include_analysis: bool = Field(
        default=True, description="Whether to include analysis sections"
    )
    include_unexplored: bool = Field(
        default=False, description="Whether to include unexplored topics"
    )


class ExportResult(BaseModel):
    """Result of export request."""

    export_id: str = Field(..., description="Unique export identifier")
    status: Literal["generating", "ready", "failed"] = Field(
        ..., description="Current export status"
    )
    download_url: str | None = Field(
        default=None, description="URL to download when ready"
    )
    expires_at: datetime | None = Field(
        default=None, description="When the download URL expires"
    )
    filename: str | None = Field(
        default=None, description="Suggested filename for download"
    )


class PartialStream(BaseModel):
    """Partial stream state for recovery."""

    stream_id: str = Field(..., description="ID of the interrupted stream")
    chunks: list[str] = Field(
        default_factory=list, description="Chunks received before disconnect"
    )
    metadata: dict = Field(default_factory=dict, description="Stream metadata")


class SessionReconnectState(BaseModel):
    """State for SSE reconnection recovery."""

    session: Session = Field(..., description="The session being reconnected")
    active_exploration: Exploration | None = Field(
        default=None, description="Active exploration at disconnect time"
    )
    current_navigation: NavigationState | None = Field(
        default=None, description="Navigation state at disconnect time"
    )
    partial_stream: PartialStream | None = Field(
        default=None, description="Partial stream state if streaming was interrupted"
    )
