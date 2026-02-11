# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date as date_type
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# =============================================================================
# Constants
# =============================================================================

DEFAULT_CONTEXT_ID = "bundestagswahl-2025"


# =============================================================================
# Database Entities
# =============================================================================


class ContextType(str, Enum):
    """Type of political context."""

    ELECTION = "election"
    GENERAL = "general"


class Context(BaseModel):
    """
    A political context representing either an election or a general political level.

    Examples:
    - Elections: "bundestagswahl-2025", "nrw-landtagswahl-2027"
    - General: "bundesebene", "landesebene-bayern"
    """

    context_id: str = Field(..., description="Unique identifier for the context")
    name: str = Field(..., description="Display name (e.g., 'Bundestagswahl 2025')")
    short_name: str = Field(..., description="Short name of the context")
    type: ContextType = Field(..., description="Type: election or general")
    date: date_type | None = Field(
        None, description="Relevant date (e.g., election date for elections)"
    )
    location_name: str = Field(
        ..., description="Location for the context as used in the prompt"
    )
    is_active: bool = Field(
        True, description="Whether this context is currently active"
    )
    icon_url: str | None = Field(None, description="Icon URL for the context")
    supports_swiper: bool = Field(
        ..., description="Whether the context supports the swiper"
    )
    supports_voting_behavior: bool = Field(
        ..., description="Whether the context supports voting behavior"
    )
    relevant_area: str | None = Field(
        ...,
        description="Relevant area for the context to check which is the most relevant context for a user",
    )


class ContextParty(BaseModel):
    """
    A party within a specific context (stored as sub-collection of Context).

    The same party (e.g., SPD) can have different configurations
    in different contexts (different candidates, manifestos, etc.).

    Firestore path: contexts/{context_id}/parties/{party_id}
    """

    party_id: str = Field(..., description="Party identifier (e.g., 'spd', 'cdu')")
    name: str = Field(..., description="Short name (e.g., 'SPD')")
    long_name: str = Field(
        ..., description="Full name (e.g., 'Sozialdemokratische Partei...')"
    )
    manifesto_url: str | None = Field(
        None, description="URL to the election manifesto/program"
    )
    candidate: str | None = Field(
        None, description="Lead candidate (mainly for elections)"
    )
    website_url: str = Field(..., description="Party website URL")
    is_already_in_parliament: bool = Field(
        True, description="Whether the party is currently in parliament"
    )
    is_small_party: bool = Field(
        False, description="Whether the party is a small party"
    )
    description: Optional[str] = Field(None, description="Party description")
    background_color: str = Field(
        "#808080", description="Brand color for UI (hex format)"
    )
    logo_src: str = Field("", description="URL/path to party logo")
