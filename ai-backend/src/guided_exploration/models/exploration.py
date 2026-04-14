# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Models for exploration state and summary tree in guided exploration."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.guided_exploration.models.content import Citation
from src.guided_exploration.models.conversation import LeafSummary
from src.guided_exploration.models.tree import ExplorationTree


# =============================================================================
# Per-Party Knowledge Models (kept for conversation handler context)
# =============================================================================


class ExtractedPositionItem(BaseModel):
    """A single position extracted from party documents with source quote."""

    position: str = Field(..., description="The extracted position in own words")
    quote: str = Field(..., description="Verbatim quote from source document")
    source_doc: str = Field(..., description="Source document name")
    source_page: int | None = Field(
        default=None, description="Page number if available"
    )
    position_type: str = Field(
        default="position",
        description="Type: position, measure, target, argument, criticism",
    )
    citation_id: str | None = Field(
        default=None,
        description="ID of the citation for this position (set during knowledge resolution)",
    )


class ExtractedPosition(BaseModel):
    """Structured extraction of a party's position from documents."""

    party_id: str = Field(..., description="Party ID")
    summary: str = Field(default="", description="1-sentence summary")
    positions: list[ExtractedPositionItem] = Field(
        default_factory=list,
        description="All extracted positions with quotes",
    )


class RetrievedChunk(BaseModel):
    """A chunk retrieved from RAG."""

    chunk_id: str = Field(..., description="Unique identifier for the chunk")
    content: str = Field(..., description="The text content of the chunk")
    party_id: str = Field(..., description="Party ID this chunk belongs to")
    source_document: str = Field(..., description="Source document name/path")
    source_section: str | None = Field(
        default=None, description="Section within the document"
    )
    source_page: int | None = Field(
        default=None, description="Page number if applicable"
    )
    relevance_score: float = Field(
        ..., description="Relevance score from RAG retrieval"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ExplorationStatus(str, Enum):
    """Status of an exploration."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SummaryTree(BaseModel):
    """Parallel tree tracking summaries."""

    exploration_id: Optional[str] = Field(
        None, description="ID of the parent exploration"
    )
    summaries: dict[str, LeafSummary] = Field(
        default_factory=dict, description="Mapping of leaf_id to summary"
    )
    topic_summaries: dict[str, str] = Field(
        default_factory=dict, description="Mapping of topic_id to aggregated summary"
    )


class FinalSummary(BaseModel):
    """Generated when exploration completes."""

    closing_summary: str = Field(..., description="Closing summary of the exploration")
    overview: str = Field(..., description="High-level overview")
    key_findings: list[str] = Field(
        default_factory=list, description="Key findings from the exploration"
    )
    generated_at: datetime = Field(..., description="When the summary was generated")


class Exploration(BaseModel):
    """Full exploration state."""

    id: str = Field(..., description="Unique exploration identifier")
    session_id: str = Field(..., description="ID of the owning session")
    original_query: str = Field(
        ..., description="The user's original query that started this exploration"
    )
    tree: ExplorationTree = Field(
        ..., description="The position-based exploration tree"
    )
    status: ExplorationStatus = Field(
        default=ExplorationStatus.ACTIVE, description="Current status"
    )
    final_summary: FinalSummary | None = Field(
        default=None, description="Final summary when exploration completes"
    )
    created_at: datetime = Field(..., description="When the exploration was created")
    updated_at: datetime = Field(
        ..., description="When the exploration was last updated"
    )


class ResolvedKnowledge(BaseModel):
    """Pre-processed knowledge context for a leaf (cached)."""

    leaf_id: str = Field(..., description="ID of the leaf node")
    party_positions: dict[str, ExtractedPosition] = Field(
        default_factory=dict, description="Mapping of party_id to extracted position"
    )
    citation_pool: list[Citation] = Field(
        default_factory=list, description="Available citations"
    )
    party_chunks: dict[str, list["RetrievedChunk"]] = Field(
        default_factory=dict,
        description="Mapping of party_id to retrieved chunks for this subtopic",
    )


