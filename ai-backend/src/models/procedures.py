# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Chat-facing procedure types.

The stored record lives in ``wahlchat_common.procedures`` (ingestion writes
it, this service reads it). ``ProcedureView`` is what a consumer gets for one
procedure: the record plus the chunks that point to it.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from wahlchat_common.procedures import ProcedureRecord, ProcedureSummary

__all__ = ["DrucksacheStrategy", "ProcedureRecord", "ProcedureSummary", "ProcedureView"]

# How Drucksache text is searched (ADR-0013): S1 overview chunks only, S2
# overview and body alike, S3 overview first and the body of the procedures
# the overview hits belong to.
DrucksacheStrategy = Literal["S1", "S2", "S3"]


class ProcedureView(BaseModel):
    """One procedure with its votes, speeches and Drucksache chunks, oldest first."""

    procedure: ProcedureRecord
    votes: list[dict[str, Any]] = Field(default_factory=list)
    speeches: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
