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
    suggested_followups: list[str] = Field(
        default_factory=list,
        description=(
            "Quick-reply chips offered alongside this assistant turn. "
            "Persisted so the study admin can audit what the participant "
            "was offered next to each message."
        ),
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


class FlaggedCitation(BaseModel):
    """One occurrence of an LLM citing an id outside the leaf's pool.

    Recorded for analysis — the response itself still ships to the user;
    the offending ids just don't survive the ``extract_used_citations``
    intersection so they're never logged as exposure.
    """

    exploration_id: str | None = Field(
        default=None, description="Exploration the response belonged to, if any"
    )
    leaf_id: str | None = Field(
        default=None, description="Leaf id the response was scoped to, if any"
    )
    message_id: str | None = Field(
        default=None,
        description="Assistant message id the fabrication appeared in, if any",
    )
    handler: str = Field(
        ...,
        description="Which handler produced the response (leaf followup, quick_summary, baseline)",
    )
    fabricated_ids: list[str] = Field(
        default_factory=list,
        description="Citation ids the LLM bracketed that weren't in the pool",
    )
    pool_size: int = Field(
        default=0, description="Size of the citation pool the response had access to"
    )
    occurred_at: datetime = Field(..., description="When the fabrication was detected")


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
    max_claims_per_party: int | None = Field(
        default=None,
        description=(
            "Optional cap on how many claims the baseline summary handler "
            "may surface per party in a single response. Set on session "
            "creation by the study facade for the capped-baseline arm "
            "(C groups). None = no cap."
        ),
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
    flagged_citations: list[FlaggedCitation] = Field(
        default_factory=list,
        description="Citation fabrications detected on responses in this session",
    )
    active_exploration_id: str | None = Field(
        default=None,
        description="ID of the currently active exploration, if any",
    )


class SessionInfo(BaseModel):
    """Response when creating/resuming session."""

    session_id: str = Field(..., description="The session ID")
    stream_url: str = Field(..., description="URL for SSE connection")
    active_exploration: Exploration | None = Field(
        default=None, description="Currently active exploration if any"
    )


