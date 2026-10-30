# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shapes of the parliament feed: one ``FeedItem`` per debate (agenda item)
or vote (poll), and one ``FeedEdition`` per parliament and sitting day that
lists them in order."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ingestion.feed.parliaments import ParliamentId
from ingestion.feed.topics import DigestTopic


class DigestVoteParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    name: str
    color: str
    yes: int
    no: int
    abstain: int
    no_show: int


class DigestCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    # Set when the citation is a speech: who gave it, for which party, and
    # the speech's own video file when openparliament.tv has aligned it.
    speaker: Optional[str] = None
    party_id: Optional[str] = None
    party_name: Optional[str] = None
    color: Optional[str] = None
    video_url: Optional[str] = None


class DigestSpeaker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    # The speech in the Plenarprotokoll PDF, opened at its page when known.
    url: Optional[str] = None
    # The speech's own video file, and the link to it at the speech's start.
    video_url: Optional[str] = None
    video_link: Optional[str] = None


class DigestQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    speaker: str
    party_id: str
    party_name: str


class DigestProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    pdf_url: Optional[str] = None


def edition_doc_id(parliament: str, day: date) -> str:
    return f"{parliament}_{day.isoformat()}"


# ---------------------------------------------------------------------------
# Published shape: one feed item per debate or vote, the unit every surface
# (feed, briefings, social posts) reuses. Mirrored by ``FeedItem`` and
# ``FeedEdition`` in ``web/lib/firebase/firebase.types.ts``.
#
# ``facts`` come from the source data and are identical in every language;
# ``content`` holds the texts per locale. German is generated from the German
# protocols; every other locale is a translation of it, valid while its
# ``source_hash`` matches the German text it was made from.
# ---------------------------------------------------------------------------

Locale = Literal["de", "en"]
CANONICAL_LOCALE: Locale = "de"
TRANSLATED_LOCALES: tuple[Locale, ...] = ("en",)
FeedItemKind = Literal["debate", "vote"]
FeedItemStatus = Literal["published", "retracted"]

# Bump when the stored feed shape gains or changes a field. Part of every
# item's input_hash, so stored items are rebuilt in the new shape.
FEED_FORMAT_VERSION = "2"


class LocalizedPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    text: str


class LocalizedContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Doubles as the callout of a social post.
    headline: str
    teaser: Optional[str] = None
    key_points: list[str] = Field(default_factory=list)
    positions: list[LocalizedPosition] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    # The opening quote stays verbatim German in ``facts``; other locales carry
    # a faithful translation next to it, never in place of it.
    quote_translation: Optional[str] = None
    origin: Literal["generated", "translated"]
    # Hash of the German content this text was made from (for German itself,
    # its own hash), so a stale translation is detectable without a diff.
    source_hash: str
    prompt_version: str
    generated_by: Optional[str] = None
    generated_at: datetime


class DebateParty(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    party_name: str
    color: str
    speakers: list[DigestSpeaker]


class DebateFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocols: list[DigestProtocol]
    agenda_item: str = Field(description="The official German agenda label.")
    citations: list[DigestCitation]
    # Every Fraktion that spoke, from the source, in order of first speech. A
    # party whose position could not be written and verified stays here
    # without an entry in ``content.positions``.
    parties: list[DebateParty] = Field(default_factory=list)
    video_url: Optional[str] = None
    heat: Optional[int] = Field(None, ge=1, le=5)
    debate_minutes: Optional[int] = None
    opened_by: Optional[str] = None
    opening_quote: Optional[DigestQuote] = None


class VoteFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_id: int
    official_title: str
    outcome: Optional[str] = None
    citation_url: Optional[str] = None
    description: Optional[str] = Field(
        None, description="The source's own German account of the motion."
    )
    parties: list[DigestVoteParty]


class FeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: FeedItemKind
    edition_id: str
    parliament: ParliamentId
    parliament_name: str
    region: str
    date: date
    # Position within its edition: debates in agenda order, then votes. The
    # page ranks by heat and length on its own.
    rank: int
    topics: list[DigestTopic] = Field(min_length=1)
    status: FeedItemStatus = "published"
    debate: Optional[DebateFacts] = None
    vote: Optional[VoteFacts] = None
    content: dict[Locale, LocalizedContent]
    # Hash of this item's own sources + prompt and format version. None when a
    # step fell back or a position is missing, so the next run retries it.
    input_hash: Optional[str] = None
    format_version: str = FEED_FORMAT_VERSION
    generated_at: datetime


class FeedEdition(BaseModel):
    """One parliament's sitting day as published: its items, in order."""

    model_config = ConfigDict(extra="forbid")

    id: str
    parliament: ParliamentId
    parliament_name: str
    region: str
    date: date
    protocols: list[DigestProtocol] = Field(default_factory=list)
    item_ids: list[str]
    format_version: str = FEED_FORMAT_VERSION
    generated_at: datetime
