# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for party knowledge resolver agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.exploration import PartyKnowledge, RetrievedChunk
from src.guided_exploration.models.tree import TopicTree


class PartyKnowledgeResolverInput(BaseModel):
    """Input for single-party knowledge resolution."""

    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    party_id: str = Field(..., description="Party ID to resolve knowledge for")
    party_info: PartyInfo = Field(..., description="Information about the party")
    topic_tree: TopicTree = Field(..., description="The combined topic tree")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for this party",
    )
    party_coverage: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapping of subtopic_id to party_ids that cover it",
    )


class PartyKnowledgeResolverOutput(BaseModel):
    """Output: knowledge for this party across all subtopics."""

    party_id: str = Field(..., description="Party ID this output is for")
    party_knowledge: PartyKnowledge = Field(
        ..., description="Knowledge resolved for this party"
    )
