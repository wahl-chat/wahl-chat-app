# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for party claims extracted from election manifestos."""

from typing import Literal

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Citation


class Claim(BaseModel):
    """A concrete position, demand, measure, or statement from a party."""

    id: str = Field(..., description="Unique claim ID, e.g., 'spd-mindestlohn-001'")
    party_id: str = Field(..., description="Party this claim belongs to")
    content: str = Field(
        ...,
        description=(
            "The concrete position or demand. Should be a discrete, quotable "
            "statement — not an abstract topic."
        ),
    )
    quote: str = Field(
        default="",
        description="Verbatim quote from the source document supporting this claim",
    )
    claim_type: Literal[
        "position", "measure", "target", "argument", "criticism"
    ] = Field(
        default="position",
        description="Type of claim",
    )
    citation: Citation | None = Field(
        default=None, description="Source reference for this claim"
    )
    chunk_index: int = Field(
        default=-1,
        description="Index into the retrieved chunks list for this party",
    )


class PartyClaims(BaseModel):
    """All claims extracted from a single party's documents."""

    party_id: str = Field(..., description="Party ID")
    claims: list[Claim] = Field(
        default_factory=list, description="All extracted claims"
    )
    relevance_to_query: float = Field(
        default=0.5,
        description="How relevant this party's content is to the query (0.0-1.0)",
    )
