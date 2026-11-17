# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Contracts of the generic chat: the request anchor, tool inputs and outputs,
the numbered source registry, and the agent's per-turn dependencies."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.context import Context, ContextParty
from wahlchat_common.answer_rules import AnswerLanguage

# Feed item ids as the feed builder writes them:
# "{parliament}_{YYYY-MM-DD}_v{poll_id}" or "..._d{session}-{agenda_slug}".
FEED_ITEM_ID_PATTERN = r"^[a-z][a-z_]{0,40}_\d{4}-\d{2}-\d{2}_(v\d{1,9}|d\d{1,4}-[a-z0-9]{0,20})$"
# DIP Vorgang ids are numeric.
VORGANG_ID_PATTERN = r"^\d{1,12}$"

SearchSourceType = Literal["vote_record", "parliamentary_speech", "party_manifesto"]
FeedItemKind = Literal["debate", "vote"]


class Anchor(BaseModel):
    """The feed item, poll or procedure a conversation is about. Exactly one
    field is set."""

    model_config = ConfigDict(extra="forbid")

    feed_item_id: Optional[str] = Field(
        None, max_length=120, pattern=FEED_ITEM_ID_PATTERN
    )
    poll_id: Optional[int] = Field(None, ge=1, le=10**9)
    vorgang_id: Optional[str] = Field(None, pattern=VORGANG_ID_PATTERN)

    @model_validator(mode="after")
    def _exactly_one(self) -> Anchor:
        given = [self.feed_item_id, self.poll_id, self.vorgang_id]
        if sum(value is not None for value in given) != 1:
            raise ValueError("anchor needs exactly one of feed_item_id, poll_id, vorgang_id")
        return self


# ---------------------------------------------------------------------------
# Tool inputs (the JSON schemas the model sees)
# ---------------------------------------------------------------------------


class SearchInput(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=300,
        description="German search query, e.g. 'Mietpreisbremse Verlängerung'.",
    )
    source_types: Optional[list[SearchSourceType]] = Field(
        None,
        description="Limit to these source types; all three when omitted.",
    )
    party_id: Optional[str] = Field(
        None,
        max_length=40,
        description=(
            "Party slug (e.g. 'spd') to limit to one party's sources; when"
            " omitted in a chat with a party focus, each focus party is searched."
        ),
    )
    since: Optional[date] = Field(
        None, description="Earliest publish date; only when the question names a period."
    )
    until: Optional[date] = Field(
        None, description="Latest publish date; only when the question names a period."
    )
    wahlperiode: Optional[int] = Field(
        None,
        ge=1,
        le=99,
        description=(
            "Bundestag term to search exactly, e.g. 20 for 'im letzten Bundestag';"
            " only when the question names a period."
        ),
    )


class GetVoteInput(BaseModel):
    poll_id: int = Field(ge=1, le=10**9, description="abgeordnetenwatch poll id.")


class GetDebateInput(BaseModel):
    feed_item_id: str = Field(
        max_length=120,
        pattern=FEED_ITEM_ID_PATTERN,
        description="Feed item id from list_feed_items or the conversation anchor.",
    )


class GetProcessInput(BaseModel):
    vorgang_id: Optional[str] = Field(
        None,
        pattern=VORGANG_ID_PATTERN,
        description="DIP procedure id, e.g. from a search result's procedures.",
    )
    name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=200,
        description="The law's or motion's name as the user gave it, e.g. 'Wehrdienstgesetz'.",
    )
    question: Optional[str] = Field(
        None,
        max_length=300,
        description="What the user wants to know about it, in German; picks the Drucksache passages.",
    )
    party_id: Optional[str] = Field(
        None,
        max_length=40,
        description="Party slug to keep only its speeches and the Drucksachen it tabled.",
    )

    @model_validator(mode="after")
    def _id_or_name(self) -> GetProcessInput:
        if (self.vorgang_id is None) == (self.name is None):
            raise ValueError("give exactly one of vorgang_id, name")
        return self


class ListFeedItemsInput(BaseModel):
    since: date = Field(description="First day of the window (inclusive).")
    until: date = Field(description="Last day of the window (inclusive).")
    kind: Optional[FeedItemKind] = Field(None, description="Only debates or votes.")


class WebSearchInput(BaseModel):
    query: str = Field(min_length=2, max_length=300, description="Search query.")
    scope: Literal["news", "civic"] = Field(
        description=(
            "'news' for current events (preferred outlets first, then the open "
            "web); 'civic' for how German politics and institutions work "
            "(official sites only)."
        )
    )
    recency: Optional[Literal["day", "week", "month", "year"]] = None


# ---------------------------------------------------------------------------
# Tool outputs (what the model reads back)
# ---------------------------------------------------------------------------


class ProcedureRef(BaseModel):
    vorgang_id: str
    title: str
    latest_stage: Optional[str] = None


class NumberedDocument(BaseModel):
    """One citable source as the model sees it; ``id`` is the citation number."""

    id: int
    source_type: str
    title: Optional[str] = None
    date: Optional[str] = None
    party: Optional[str] = None
    outlet: Optional[str] = None
    preferred_outlet: Optional[bool] = None
    wahlperiode: Optional[int] = None
    period: Optional[Literal["recent", "earlier"]] = None
    # Procedures the source belongs to, for a follow-up get_process.
    procedures: Optional[list[ProcedureRef]] = None
    text: str


class ToolResult(BaseModel):
    documents: list[NumberedDocument] = Field(default_factory=list)
    note: Optional[str] = None


class FeedItemSummary(BaseModel):
    """A feed item for orientation only; never a citable source."""

    feed_item_id: str
    kind: str
    date: str
    headline: str
    agenda_item: Optional[str] = None
    poll_id: Optional[int] = None
    outcome: Optional[str] = None


class DebateResult(ToolResult):
    item: Optional[FeedItemSummary] = None


class ProcessStep(BaseModel):
    """One dated step; ``id`` cites its Drucksache or Plenarprotokoll."""

    id: Optional[int] = None
    date: str
    chamber: str
    name: str
    document: Optional[str] = None
    decisions: list[str] = Field(default_factory=list)
    summary: Optional[str] = Field(
        None, description="A checked summary of the step's Drucksache; cite the step's id"
    )


class ProcessInfo(BaseModel):
    vorgang_id: str
    title: str
    kind: str
    vorgangstyp: str
    wahlperiode: int
    beratungsstand: Optional[str] = None
    initiative: list[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    dip_url: str


class ProcessChoice(BaseModel):
    vorgang_id: str
    label: str
    latest_stage: Optional[str] = None


class ProcessResult(ToolResult):
    procedure: Optional[ProcessInfo] = None
    steps: list[ProcessStep] = Field(default_factory=list)
    choices: list[ProcessChoice] = Field(default_factory=list)


class FeedItemsResult(BaseModel):
    items: list[FeedItemSummary] = Field(default_factory=list)
    note: Optional[str] = None


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    date: Optional[str] = None
    domain: str
    preferred: bool


# ---------------------------------------------------------------------------
# Feed items as stored by the ingestion feed job (read model; only the fields
# the tools use, unknown fields ignored so newer feed formats keep validating)
# ---------------------------------------------------------------------------


class _Lenient(BaseModel):
    model_config = ConfigDict(extra="ignore")


class FeedContentView(_Lenient):
    headline: str = ""


class FeedDebateView(_Lenient):
    agenda_item: str = ""
    drucksachen: Optional[list[str]] = None
    speech_ids: Optional[list[str]] = None


class FeedVoteView(_Lenient):
    poll_id: int
    official_title: str = ""
    outcome: Optional[str] = None
    drucksachen: Optional[list[str]] = None


class FeedItemView(_Lenient):
    id: str
    kind: FeedItemKind
    parliament: str
    date: str
    status: str = "published"
    debate: Optional[FeedDebateView] = None
    vote: Optional[FeedVoteView] = None
    content: dict[str, FeedContentView] = Field(default_factory=dict)

    def headline(self, language: str) -> str:
        localized = self.content.get(language) or self.content.get("de")
        if localized and localized.headline:
            return localized.headline
        if self.vote is not None:
            return self.vote.official_title
        return self.debate.agenda_item if self.debate is not None else self.id

    def summary(self, language: str) -> FeedItemSummary:
        return FeedItemSummary(
            feed_item_id=self.id,
            kind=self.kind,
            date=self.date,
            headline=self.headline(language),
            agenda_item=self.debate.agenda_item if self.debate else None,
            poll_id=self.vote.poll_id if self.vote else None,
            outcome=self.vote.outcome if self.vote else None,
        )


# ---------------------------------------------------------------------------
# Per-turn state
# ---------------------------------------------------------------------------


@dataclass
class SourceRegistry:
    """Every source the tools surfaced this turn, in citation order.

    Entries use the chat's ``sources_ready`` dict shape. Citation numbers are
    0-based list indices, as the web resolves ``[n]`` to ``sources[n]``.
    """

    entries: list[dict] = field(default_factory=list)
    _index_by_key: dict[str, int] = field(default_factory=dict)

    def register(self, entry: dict) -> int:
        key = f"{entry.get('url')}|{entry.get('source')}|{entry.get('page')}"
        if key in self._index_by_key:
            return self._index_by_key[key]
        self.entries.append(entry)
        self._index_by_key[key] = len(self.entries) - 1
        return self._index_by_key[key]

    def snapshot(self) -> list[dict]:
        return [dict(e) for e in self.entries]


@dataclass
class AnchorContext:
    """The resolved anchor: a label for the prompt and its documents."""

    label: str
    result: ToolResult


@dataclass
class GenericChatDeps:
    context: Context
    parties: list[ContextParty]
    language: AnswerLanguage
    session_id: str
    sources: SourceRegistry = field(default_factory=SourceRegistry)
    anchor: Optional[AnchorContext] = None
    # Parties the user pinned for the whole chat, a subset of ``parties``.
    focus: list[ContextParty] = field(default_factory=list)
    # Procedures a name left open this turn; shown as quick replies.
    choices: list[ProcessChoice] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)

    def set_focus(self, party_ids: list[str]) -> None:
        """Keeps the ids the context knows, in request order."""
        by_id = {party.party_id: party for party in self.parties}
        self.focus = [by_id[pid] for pid in dict.fromkeys(party_ids) if pid in by_id]

    def party_name(self, party_id: Optional[str]) -> Optional[str]:
        if party_id is None:
            return None
        for party in self.parties:
            if party.party_id == party_id:
                return party.name
        return party_id
