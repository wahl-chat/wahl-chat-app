# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import List, Optional
from pydantic import BaseModel, Field


class Link(BaseModel):
    """
    A link to a website.
    """

    url: str = Field(..., description="The URL of the link")
    title: str = Field(..., description="The title of the link")


class VotingResultsOverall(BaseModel):
    """
    The overall voting results.
    """

    yes: int = Field(..., description="The number of yes votes")
    no: int = Field(..., description="The number of no votes")
    abstain: int = Field(..., description="The number of abstain votes")
    not_voted: int = Field(..., description="The number of not voted votes")
    members: int = Field(..., description="The number of members")


class VotingResultsByParty(BaseModel):
    """
    The voting results by party.
    """

    party: str = Field(..., description="The id of the party")
    members: int = Field(..., description="The number of members")
    yes: int = Field(..., description="The number of yes votes")
    no: int = Field(..., description="The number of no votes")
    abstain: int = Field(..., description="The number of abstain votes")
    not_voted: int = Field(..., description="The number of not voted votes")
    justification: str | None = Field(
        description="The justification of the vote", default=None
    )


class VotingResults(BaseModel):
    """
    The voting results of a vote.
    """

    overall: VotingResultsOverall = Field(..., description="The overall voting results")
    by_party: List[VotingResultsByParty] = Field(
        ..., description="The voting results by party"
    )


class Vote(BaseModel):
    """
    A vote from the Bundestag on a specific topic.
    """

    id: str = Field(..., description="The ID of the vote")
    url: str = Field(..., description="The URL of the vote")
    date: str = Field(..., description="The date of the vote")
    title: str = Field(..., description="The title of the vote")
    subtitle: Optional[str] = Field(..., description="The subtitle of the vote")
    detail_text: Optional[str] = Field(..., description="The detail text of the vote")
    links: List[Link] = Field(..., description="The links of the vote")
    voting_results: VotingResults = Field(
        ..., description="The voting results of the vote"
    )
    short_description: Optional[str] = Field(
        ..., description="The short description of the vote"
    )
    vote_category: Optional[str] = Field(..., description="The category of the vote")
    submitting_parties: Optional[list[str]] = Field(
        ..., description="The ids of the parties submitting the vote"
    )
