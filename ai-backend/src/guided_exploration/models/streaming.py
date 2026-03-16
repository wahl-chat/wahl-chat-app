# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Streaming models for agents in guided exploration."""

from pydantic import BaseModel, Field


class StreamChunk(BaseModel):
    """Chunk emitted by streaming agents."""

    content: str = Field(..., description="The content of this chunk")
    section: str | None = Field(
        default=None,
        description="For structured content: summary, party_positions, etc.",
    )
    is_final: bool = Field(default=False, description="Whether this is the final chunk")
    metadata: dict = Field(
        default_factory=dict, description="Additional metadata for the chunk"
    )
