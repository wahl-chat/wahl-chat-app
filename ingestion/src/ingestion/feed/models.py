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


class SpeechSource(BaseModel):
    """The passage of one speech a bullet or position draws on. The model
    names the speech; the moment and sentence inside it are matched by code
    (``passages.locate``), never written by the model."""

    model_config = ConfigDict(extra="forbid")

    speaker: str
    # The speaker's own party (CSU, not the Union), as on the citations.
    party_id: str
    party_name: str
    # The speech's own video file and the second the passage starts at.
    video_url: Optional[str] = None
    start: Optional[float] = None
    # The Plenarprotokoll, its PDF page, and the sentence to highlight there.
    pdf_url: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None


class KeyPointSources(BaseModel):
    """One bullet's passages. An object rather than a bare list: Firestore
    stores no array directly inside another."""

    model_config = ConfigDict(extra="forbid")

    sources: list[SpeechSource] = Field(default_factory=list)


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
FEED_FORMAT_VERSION = "3"


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
    # Where the Fraktion's position sentence comes from; empty while it has
    # no position, and on items stored before sources were kept.
    position_sources: list[SpeechSource] = Field(default_factory=list)


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
    # Legacy model rating on items built before heat was counted; unused,
    # kept so they validate.
    heat: Optional[int] = Field(None, ge=1, le=5)
    debate_minutes: Optional[int] = None
    opened_by: Optional[str] = None
    opening_quote: Optional[DigestQuote] = None
    # The Drucksachen the agenda item deals with, from the protocol. None
    # until looked up; a vote on one of them is a vote on this debate.
    drucksachen: Optional[list[str]] = None
    # Calls from the floor, objections, mocking laughter and unrest the
    # protocol records during the debate. Per minute of debate, it is the
    # heat the page shows. None until counted.
    interjections: Optional[int] = None
    # Where each bullet of ``content.*.key_points`` comes from, by index; the
    # translation keeps the bullets' count, so one list serves every locale.
    # Empty on items stored before sources were kept.
    key_point_sources: list[KeyPointSources] = Field(default_factory=list)


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
    # The Drucksachen the poll was about, as abgeordnetenwatch links them.
    # None until looked up.
    drucksachen: Optional[list[str]] = None


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
    # page ranks by interjections per minute on its own.
    rank: int
    topics: list[DigestTopic] = Field(min_length=1)
    status: FeedItemStatus = "published"
    debate: Optional[DebateFacts] = None
    vote: Optional[VoteFacts] = None
    content: dict[Locale, LocalizedContent]
    # Hash of this item's own sources + prompt and format version. None when a
    # vote's texts fell back to its title, so the next run retries it.
    input_hash: Optional[str] = None
    # Fraktionen that spoke but have no checked position yet. Later runs retry
    # only these, up to ``MAX_POSITION_ATTEMPTS`` runs in all, and leave every
    # other text as it was written, so the card does not change from run to run.
    pending_positions: list[str] = Field(default_factory=list)
    position_attempts: int = 0
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


class PlenarySitting(BaseModel):
    """One plenary sitting on the published agenda."""

    model_config = ConfigDict(extra="forbid")

    date: date
    number: int


class SittingWeek(BaseModel):
    """A sitting week of the parliament's calendar. ``sittings`` is known only
    once the week's agenda is published, about a week ahead."""

    model_config = ConfigDict(extra="forbid")

    start: date
    end: date
    sittings: Optional[list[PlenarySitting]] = None


class SittingCalendar(BaseModel):
    """The parliament's sitting weeks from ``since`` (when the feed begins)
    to several weeks ahead: for the next-sitting status and the month grid of
    sitting days. The reader picks what is next by their own date, so the
    stored copy may age until the next run."""

    model_config = ConfigDict(extra="forbid")

    parliament: ParliamentId
    since: date
    weeks: list[SittingWeek]
    sources: list[str]
    checked_at: datetime
