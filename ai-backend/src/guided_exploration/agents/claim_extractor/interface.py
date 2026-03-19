# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for claim extractor agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models.claim import PartyClaims
from src.guided_exploration.models.exploration import RetrievedChunk


class ClaimExtractorInput(BaseModel):
    """Input for single-party claim extraction."""

    query: str = Field(..., description="The user's original query")
    context_id: str = Field(..., description="The election/political context ID")
    context_name: str = Field(..., description="Display name of the context")
    party_id: str = Field(..., description="Party ID to extract claims for")
    party_info: PartyInfo = Field(..., description="Information about the party")
    retrieved_chunks: list[RetrievedChunk] = Field(
        default_factory=list,
        description="Retrieved document chunks for this party only",
    )


class ClaimExtractorOutput(BaseModel):
    """Output: all concrete claims extracted from a party's documents."""

    party_id: str = Field(..., description="Party ID this output is for")
    party_claims: PartyClaims = Field(
        ..., description="All extracted claims for this party"
    )
