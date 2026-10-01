# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Firestore ``daily_digests/{parliament}_{YYYY-MM-DD}`` document shape.

Mirrored by ``DailyDigest`` in ``web/lib/firebase/firebase.types.ts``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.daily_digest.parliaments import ParliamentId
from src.daily_digest.topics import DigestTopic


class DigestVoteParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    name: str
    color: str
    yes: int
    no: int
    abstain: int
    no_show: int


class DigestVote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_id: int
    title: str
    short_title: str
    summary: Optional[str] = None
    topics: list[DigestTopic] = Field(min_length=1)
    outcome: Optional[str] = Field(
        None,
        description="'angenommen' | 'abgelehnt' | None when the source has no flag",
    )
    citation_url: Optional[str] = None
    parties: list[DigestVoteParty]


class DigestCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str


class DigestSessionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: DigestTopic
    headline: str
    summary: str
    agenda_items: list[str]
    citations: list[DigestCitation]
    video_url: Optional[str] = None


class DigestProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    pdf_url: Optional[str] = None


class DigestSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocols: list[DigestProtocol]
    sections: list[DigestSessionSection]
    other_topics: list[str] = Field(
        default_factory=list,
        description="Minor agenda items too small for a section of their own.",
    )


class DailyDigest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    parliament: ParliamentId
    parliament_name: str
    region: str
    date: date
    votes: list[DigestVote]
    session: Optional[DigestSession] = None
    # Hash of the source payloads + prompt version. None when any LLM step fell
    # back, so the next run regenerates that day instead of skipping it.
    input_hash: Optional[str] = None
    generated_at: datetime


def digest_doc_id(parliament: str, day: date) -> str:
    return f"{parliament}_{day.isoformat()}"
