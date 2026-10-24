# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shapes of the parliament feed.

``DailyDigest`` is what the builder produces for one sitting day, and the
shape of the ``daily_digests`` docs stored before the feed was split into
items. ``split_digest`` (``items.py``) turns it into the published
``FeedEdition`` + ``FeedItem`` docs below.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.feed.parliaments import ParliamentId
from src.feed.topics import DigestTopic


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
    description: Optional[str] = Field(
        None,
        description="The source's own account of the motion (abgeordnetenwatch intro).",
    )
    topics: list[DigestTopic] = Field(min_length=1)
    outcome: Optional[str] = Field(
        None,
        description="'angenommen' | 'abgelehnt' | None when the source has no flag",
    )
    citation_url: Optional[str] = None
    parties: list[DigestVoteParty]
    suggested_questions: list[str] = Field(default_factory=list)
    generated_by: Optional[str] = Field(
        None, description="Roster entry that wrote the texts; None on a fallback."
    )


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


class DigestPartyPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    party_id: str
    party_name: str
    color: str
    speakers: list[DigestSpeaker]
    position: str


class DigestQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    speaker: str
    party_id: str
    party_name: str


class DigestSessionSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: DigestTopic
    headline: str
    summary: str
    positions: list[DigestPartyPosition] = Field(default_factory=list)
    agenda_items: list[str]
    citations: list[DigestCitation]
    video_url: Optional[str] = None
    key_points: list[str] = Field(
        default_factory=list, description="Exactly three bullets, or none."
    )
    heat: Optional[int] = Field(
        None,
        ge=1,
        le=5,
        description="How heated the debate was, relative to this sitting's other sections.",
    )
    debate_minutes: Optional[int] = Field(
        None, description="Estimated from the speeches' word count."
    )
    opening_quote: Optional[DigestQuote] = None
    opened_by: Optional[str] = Field(
        None, description="Fraktion (party id) of the debate's first speaker."
    )
    suggested_questions: list[str] = Field(default_factory=list)


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
    generated_by: Optional[str] = Field(
        None, description="Roster entry that wrote the summary."
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

# Bump when the stored feed shape gains or changes a field.
FEED_FORMAT_VERSION = "1"


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
    agenda_items: list[str] = Field(
        description="Official German agenda labels; also the source of the item id."
    )
    citations: list[DigestCitation]
    # In the same order as the positions in every locale's content.
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
    # Position within its edition: debates by importance, then votes.
    rank: int
    topics: list[DigestTopic] = Field(min_length=1)
    status: FeedItemStatus = "published"
    debate: Optional[DebateFacts] = None
    vote: Optional[VoteFacts] = None
    content: dict[Locale, LocalizedContent]
    # Keys the item had inside a ``daily_digests`` doc, so shared links and
    # recorded interest from before the split still resolve to it.
    legacy_keys: list[str] = Field(default_factory=list)
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
    other_topics: list[str] = Field(default_factory=list)
    input_hash: Optional[str] = None
    format_version: str = FEED_FORMAT_VERSION
    generated_at: datetime
