# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Payload enums stamped on every chunk by ingestion and filtered on by retrieval.

Shared because both sides must agree on the exact string values: the writer puts
them in the Qdrant payload, the reader filters on them. ``retrieve.py`` mirrors
these as ``Literal`` unions (a Python Enum in a Gemini tool declaration trips a
langchain-google-genai schema bug) — a parity test pins the two together.
"""

from __future__ import annotations

from enum import Enum


class AuthorityTier(str, Enum):
    """Trustworthiness tier for a data source item."""

    AUTHORITATIVE = "authoritative"
    FACTUAL_RECORD = "factual_record"
    SELF_REPORTED = "self_reported"
    PROMOTIONAL = "promotional"


class SourceType(str, Enum):
    """Content category of the source item."""

    PARTY_MANIFESTO = "party_manifesto"
    VOTE_RECORD = "vote_record"
    DRUCKSACHE = "drucksache"
    QA_TRANSCRIPT = "qa_transcript"
    PARLIAMENTARY_SPEECH = "parliamentary_speech"  # Bundestag plenary speeches
