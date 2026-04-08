# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for subtopic content and analysis in guided exploration."""

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Reference to source document."""

    id: str = Field(..., description="Unique identifier for the citation")
    party: str = Field(..., description="Party ID this citation belongs to")
    document: str = Field(..., description="Document name, e.g., 'Wahlprogramm 2025'")
    section: str | None = Field(default=None, description="Section within the document")
    page: int | None = Field(
        default=None, description="Page number if applicable (1-indexed for display)"
    )
    document_publish_date: str | None = Field(
        default=None, description="Publication date of the document"
    )
    url: str | None = Field(default=None, description="URL to the source document")
    source_document: str | None = Field(
        default=None, description="Full document path/identifier"
    )


class PartyPosition(BaseModel):
    """A party's position on a topic as markdown content."""

    party: str = Field(..., description="Party ID")
    content: str = Field(
        ...,
        description="Full markdown content describing the party's position with inline citations",
    )


class Analysis(BaseModel):
    """Context, feasibility, and critical assessment."""

    summary: str = Field(..., description="Overall assessment")
    context: str = Field(..., description="Background and current situation")
    feasibility: list[str] = Field(
        default_factory=list, description="Feasibility considerations"
    )
    considerations: list[str] = Field(
        default_factory=list, description="Other critical points"
    )
    sources: list[str] = Field(
        default_factory=list, description="External sources used"
    )


class PartyStance(BaseModel):
    """A single party's stance on a comparison aspect."""

    party: str = Field(..., description="Party ID")
    stance: str = Field(..., description="Short stance description")


class ComparisonAspect(BaseModel):
    """A comparable aspect extracted across parties."""

    name: str = Field(..., description="Aspect name, e.g., 'Mindestlohn'")
    party_stances: list[PartyStance] = Field(
        default_factory=list, description="Each party's stance"
    )


class AspectComparison(BaseModel):
    """Structured comparison data for toggling between views."""

    aspects: list[ComparisonAspect] = Field(
        default_factory=list, description="Comparable aspects"
    )


class SubtopicContent(BaseModel):
    """The 4-section content for a leaf subtopic."""

    subtopic_id: str = Field(..., description="ID of the subtopic")
    path: list[str] = Field(
        ..., description="Path in tree, e.g., ['housing', 'rent-control']"
    )
    summary: str = Field(..., description="Overview summary of the subtopic")
    party_positions: list[PartyPosition] = Field(
        default_factory=list, description="Each party's position"
    )
    analysis: Analysis | None = Field(
        default=None, description="Critical analysis (generated on request)"
    )
    aspect_comparison: AspectComparison | None = Field(
        default=None, description="Aspect-based comparison (generated alongside positions)"
    )
    citations: list[Citation] = Field(
        default_factory=list, description="All citations for the content"
    )
    announcement: str | None = Field(
        default=None, description="Accessibility hint for screen readers"
    )
    suggested_questions: list[str] = Field(
        default_factory=list,
        description="Suggested follow-up questions for deeper exploration",
    )
