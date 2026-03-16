# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for conversation handler agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.conversation import Message
from src.guided_exploration.models.exploration import ResolvedKnowledge


class ConversationHandlerInput(BaseModel):
    """
    Input for conversation handling.

    The ConversationHandler receives ResolvedKnowledge for the current subtopic
    from the KnowledgeBase. It only references existing knowledge and does NOT
    create new subtopics or trigger additional RAG retrieval.
    """

    message: str = Field(..., description="The user's follow-up message")
    leaf_id: str = Field(..., description="ID of the current leaf node (subtopic)")
    conversation_history: list[Message] = Field(
        default_factory=list,
        description="Previous messages in the conversation",
    )
    resolved_knowledge: ResolvedKnowledge = Field(
        ..., description="Pre-resolved knowledge for this subtopic from KnowledgeBase"
    )
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Human-readable context name")
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo for all parties"
    )


class ConversationHandlerOutput(BaseModel):
    """Output from conversation handling."""

    response: str = Field(..., description="The generated response text")
    citations: list[Citation] = Field(
        default_factory=list,
        description="Citations supporting the response",
    )
    suggested_followups: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions",
    )
