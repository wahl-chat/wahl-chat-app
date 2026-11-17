# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Chat-facing procedure types.

The stored record lives in ``wahlchat_common.procedures`` (ingestion writes
it, this service reads it). ``ProcedureView`` is what a consumer gets for one
procedure: the record plus the chunks that point to it.
"""

from typing import Any

from pydantic import BaseModel, Field

from wahlchat_common.procedures import ProcedureRecord, ProcedureSummary

__all__ = ["ProcedureRecord", "ProcedureSummary", "ProcedureView"]



class ProcedureView(BaseModel):
    """One procedure with its votes, speeches and Drucksache chunks, oldest first."""

    procedure: ProcedureRecord
    votes: list[dict[str, Any]] = Field(default_factory=list)
    speeches: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
