# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for topic combiner agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.exploration import PartyTopicTree
from src.guided_exploration.models.tree import TopicTree


class TopicCombinerInput(BaseModel):
    """Input for combining party topic trees."""

    query: str = Field(..., description="The user's original query")
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    party_trees: dict[str, PartyTopicTree] = Field(
        ..., description="Mapping of party_id to their topic tree"
    )
    parties: dict[str, PartyInfo] = Field(
        ..., description="Mapping of party_id to party information"
    )


class TopicCombinerOutput(BaseModel):
    """Output: unified topic tree for exploration."""

    topic_tree: TopicTree = Field(..., description="Unified topic tree structure")
    party_coverage: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Mapping of subtopic_id to list of party_ids that cover it",
    )
