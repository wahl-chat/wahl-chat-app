# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for position extractor agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.position import PartyPositions
from src.guided_exploration.models.exploration import RetrievedChunk


class PositionExtractorInput(BaseModel):
    """Input for single-party position extraction."""

    query: str = Field(..., description="The user's original query")
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    party_id: str = Field(..., description="Party ID to extract positions for")
    party_info: PartyInfo = Field(..., description="Information about the party")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for this party only",
    )


class PositionExtractorOutput(BaseModel):
    """Output: all concrete positions extracted from a party's documents."""

    party_id: str = Field(..., description="Party ID this output is for")
    party_positions: PartyPositions = Field(
        ..., description="All extracted positions for this party"
    )
