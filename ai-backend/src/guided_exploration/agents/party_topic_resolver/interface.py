# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for party topic resolver agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.exploration import PartyTopicTree, RetrievedChunk


class PartyTopicResolverInput(BaseModel):
    """Input for single-party topic resolution."""

    query: str = Field(..., description="The user's original query")
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    party_id: str = Field(..., description="Party ID to resolve topics for")
    party_info: PartyInfo = Field(..., description="Information about the party")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for this party only",
    )


class PartyTopicResolverOutput(BaseModel):
    """Output: topics this party discusses relevant to the query."""

    party_id: str = Field(..., description="Party ID this output is for")
    party_topic_tree: PartyTopicTree = Field(
        ..., description="Topic tree from this party's perspective"
    )
