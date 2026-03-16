# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for content generator agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.exploration import ResolvedKnowledge


class ContentGeneratorInput(BaseModel):
    """
    Input for content generation.

    The ContentGenerator receives ResolvedKnowledge for the specific subtopic
    from the KnowledgeBase. No RAG retrieval is needed - all knowledge is
    pre-resolved by the KnowledgeResolver.
    """

    subtopic_id: str = Field(..., description="ID of the subtopic")
    subtopic_name: str = Field(..., description="Display name of the subtopic")
    path: list[str] = Field(
        ..., description="Path in tree, e.g., ['wohnen', 'mietpreisbremse']"
    )
    resolved_knowledge: ResolvedKnowledge = Field(
        ..., description="Pre-resolved knowledge for this subtopic from KnowledgeBase"
    )
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Human-readable context name")
    parties_info: dict[str, PartyInfo] = Field(
        ..., description="Map of party_id -> PartyInfo for all parties"
    )
    parties: list[str] = Field(
        default_factory=list,
        description="Optional party filter - if empty, use all parties",
    )
