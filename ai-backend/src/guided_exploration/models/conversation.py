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


class TopicSwitchProposal(BaseModel):
    """A neighbour-leaf switch proposal emitted alongside an assistant turn.

    Lives at the model layer (not the agent layer) because it's persisted
    on the Message and read back by both the leaf-followup generator and
    the leaf conversation handler on subsequent turns.
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
    suggested_followups: list[str] = Field(
        default_factory=list,
        description=(
            "Follow-up chips emitted alongside this assistant turn. "
            "Persisted so later turns can see what was offered."
        ),
    )
    closure_ready: bool = Field(
        default=False,
        description=(
            "Whether the leaf was deemed substantially explored at this "
            "turn. Persisted so a later turn can see prior closure "
            "offerings — if the user kept exploring after a closure pill, "
            "the next turn should not re-offer closure unless something "
            "substantially new has happened."
        ),
    )
    topic_switch_proposal: TopicSwitchProposal | None = Field(
        default=None,
        description=(
            "Neighbour-leaf switch proposal emitted alongside this "
            "assistant turn, if any. Persisted so the same switch is not "
            "offered again on every subsequent turn."
        ),
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
