# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for the leaf conversation handler agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.conversation import Message
from src.guided_exploration.models.exploration import ResolvedKnowledge


class LeafConversationHandlerInput(BaseModel):
    """
    Input for in-leaf follow-up conversation handling.

    The agent receives ``ResolvedKnowledge`` for the current subtopic.
    It only references existing knowledge and does NOT create new
    subtopics or trigger additional RAG retrieval.
    """

    message: str = Field(..., description="The user's follow-up message")
    leaf_id: str = Field(..., description="ID of the current leaf node")
    leaf_name: str = Field(
        default="", description="Display name of the current leaf node"
    )
    leaf_description: str = Field(
        default="",
        description="Description of the leaf node — what this comparison point covers",
    )
    conversation_history: list[Message] = Field(
        default_factory=list,
        description="Previous messages in the conversation",
    )
    resolved_knowledge: ResolvedKnowledge = Field(
        ..., description="Pre-resolved knowledge for this subtopic"
    )
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Human-readable context name")
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo for all parties"
    )
    already_cited_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Citation IDs already shown to the user in this leaf — initial-"
            "content positions plus citations from prior assistant follow-ups. "
            "Used to let the model bail out gracefully when a turn would only "
            "rehash known material."
        ),
    )
    neighboring_leaves: str = Field(
        default="",
        description=(
            "Pre-formatted Markdown list of the OTHER leaves in the same "
            "exploration tree (sibling subtopics). Injected verbatim into the "
            "user prompt so the model knows which neighboring topics are "
            "off-scope for this leaf and should redirect rather than absorb "
            "their content."
        ),
    )
