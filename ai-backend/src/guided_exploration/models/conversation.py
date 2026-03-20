# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for conversations within leaf nodes in guided exploration."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Analysis, Citation, SubtopicContent


class MessageType(str, Enum):
    """Type of message in a conversation."""

    INITIAL_CONTENT = "initial_content"
    FOLLOWUP = "followup"
    ANALYSIS = "analysis"


class MessageRole(str, Enum):
    """Role of the message author."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """A single message in a conversation."""

    id: str = Field(..., description="Unique message identifier")
    role: MessageRole = Field(..., description="Who sent the message")
    type: MessageType = Field(..., description="Type of message content")
    content: str | SubtopicContent | Analysis = Field(
        ...,
        description="String for followups, SubtopicContent for initial, Analysis for analysis",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations for this message (persisted for reload)",
    )
    timestamp: datetime = Field(..., description="When the message was sent")


class Conversation(BaseModel):
    """Conversation for a leaf node."""

    leaf_id: str = Field(
        ..., description="ID of the leaf node, e.g., 'housing.rent-control'"
    )
    messages: list[Message] = Field(
        default_factory=list, description="Messages in the conversation"
    )
    has_summary: bool = Field(
        default=False, description="Whether a summary has been generated"
    )


class LeafSummary(BaseModel):
    """Summary generated for a leaf conversation."""

    leaf_id: str = Field(..., description="ID of the summarized leaf")
    overview: str = Field(..., description="2-3 sentence overview")
    key_points: list[str] = Field(
        default_factory=list, description="Main takeaways from the conversation"
    )
    party_comparison: str | None = Field(
        default=None, description="Brief comparison of party positions"
    )
    generated_at: datetime = Field(..., description="When the summary was generated")
