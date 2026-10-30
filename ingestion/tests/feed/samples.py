# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Corpus payloads, a scripted model and the feed items built from them,
shared by the feed tests."""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional

from ingestion.feed.builder import FeedBuilder, build_day, plan_days
from ingestion.feed.models import FeedItem
from ingestion.feed.parliaments import PARLIAMENTS, PartyDisplay
from ingestion.feed.prompts import (
    DebateDraft,
    OpeningQuoteDraft,
    PartyPositionDraft,
    PositionCheck,
    PositionCheckBatch,
    PositionsDraft,
    VoteEnrichment,
    VoteEnrichmentBatch,
)
from ingestion.feed.reader import SittingDay, assemble_speeches, group_sitting_days

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAY = date(2026, 9, 24)
BUNDESTAG = PARLIAMENTS["bundestag"]
DISPLAY = {
    "cdu": PartyDisplay("CDU/CSU", "#000000"),
    "spd": PartyDisplay("SPD", "#E4001B"),
    "afd": PartyDisplay("AfD", "#009EE0"),
}

_PARTIES_RE = re.compile(r"keine andere: (.*?)\. Partei-Kennungen", re.DOTALL)
_CHECK_RE = re.compile(r"^\[(P\d+)\] (\S+): (.*)$", re.MULTILINE)
_AGENDA_RE = re.compile(r"Tagesordnungspunkt „(.*?)“")


def speech(
    sid: str,
    *,
    speaker: str,
    party: str,
    text: str,
    agenda: str = "top1",
    session: int = 45,
    day: str = "2026-09-24",
    title: Optional[str] = "Wohnungsbau",
    chunk_hash: Optional[str] = None,
) -> dict:
    slug = speaker.lower().replace(" ", "-")
    return {
        "source_item_id": sid,
        "source": "op",
        "speech_key": f"de-21-{session}-{slug}-{agenda}",
        "text": text,
        "chunk_index": 0,
        "publish_date": day,
        "party_id": party,
        "citation_url": f"https://video/{sid}.mp4#t=3",
        "citation_title": f"{speaker}, {day} (Video)",
        "content_hash": chunk_hash or f"h-{sid}",
        "meta": {
            "agenda_item_title": title,
            "video_uri": f"https://video/{sid}.mp4",
            "speaker_name": speaker,
            "protocol_id": f"21/{session}",
            "transcript_pdf_url": f"https://dserver.bundestag.de/btp/21/21{session:03d}.pdf",
        },
    }


def vote(poll_id: int, day: str = "2026-09-24") -> dict:
    return {
        "external_id": poll_id,
        "publish_date": day,
        "citation_title": f"Antrag {poll_id}",
        "citation_url": f"https://www.abgeordnetenwatch.de/poll/{poll_id}",
        "text": f"Antrag {poll_id}\n\nKontext: Worum es geht.",
        "content_hash": f"vote-{poll_id}",
        "meta": {
            "motion_outcome": "angenommen",
            "vote_results": [
                {"party_id": "cdu", "yes": 200, "no": 0, "abstain": 0, "no_show": 8},
                {"party_id": "spd", "yes": 110, "no": 3, "abstain": 1, "no_show": 6},
                {
                    "party_id": "fraktionslos",
                    "yes": 0,
                    "no": 2,
                    "abstain": 0,
                    "no_show": 1,
                },
            ],
        },
    }


def default_speeches() -> list[dict]:
    return [
        speech("s1", speaker="Anna", party="spd", text="Wir brauchen mehr Wohnungen."),
        speech("s2", speaker="Bernd", party="cdu", text="Erst die Kosten prüfen."),
        speech("s3", speaker="Clara", party="csu", text="Bayern baut schon."),
        speech(
            "s4",
            speaker="Dora",
            party="afd",
            text="Weniger Vorschriften.",
            agenda="top2",
            title="Bauordnung",
        ),
    ]


def sittings(
    payloads: Optional[list[dict]] = None, *, ordered: bool = True
) -> dict[date, SittingDay]:
    """Speeches grouped like the reader does; ``ordered`` stands in for a
    protocol that put them in order (in the order given here)."""
    payloads = default_speeches() if payloads is None else payloads
    days = group_sitting_days(assemble_speeches(payloads))
    position = {p["source_item_id"]: n for n, p in enumerate(payloads)}
    for sitting in days.values():
        for item in sitting.agenda_items:
            if ordered:
                item.speeches.sort(key=lambda s: position[s.source_item_id])
            item.ordered = ordered
    return days


def _first_speech(prompt: str) -> tuple[str, str]:
    for line in prompt.splitlines():
        if line.startswith("- ") and " (" in line and "): " in line:
            name, rest = line[2:].split(" (", 1)
            return name, rest.split("): ", 1)[1]
    return "", ""


class FakeLLM:
    """Answers each schema like a cooperative model, unless told otherwise.

    ``omit`` leaves Fraktionen out of the debate's positions, ``retry_omit``
    out of the retry too; ``reject`` makes the check refuse a sentence that
    contains it; ``fail`` makes calls for those schemas raise.
    """

    def __init__(
        self,
        *,
        omit: tuple[str, ...] = (),
        retry_omit: tuple[str, ...] = (),
        reject: tuple[str, ...] = (),
        fail: tuple[type, ...] = (),
        heat: Optional[int] = 3,
        quote: Optional[OpeningQuoteDraft] = None,
        topics: Optional[list[Any]] = None,
        key_points: Optional[list[str]] = None,
    ) -> None:
        self.omit = omit
        self.retry_omit = retry_omit
        self.reject = reject
        self.fail = fail
        self.heat = heat
        self.quote = quote
        self.topics = topics
        self.key_points = key_points
        self.calls: list[type] = []
        self.prompts: list[str] = []

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        self.calls.append(schema)
        prompt = messages[0].content
        self.prompts.append(prompt)
        if schema in self.fail:
            raise RuntimeError("quota")
        return self._answer(prompt, schema), "fake-model"

    def _parties(self, prompt: str) -> list[str]:
        match = _PARTIES_RE.search(prompt)
        return [p.strip() for p in match.group(1).split(",")] if match else []

    def _answer(self, prompt: str, schema: type) -> Any:
        if schema is VoteEnrichmentBatch:
            refs = re.findall(r"^\[(V\d+)\]", prompt, re.MULTILINE)
            return VoteEnrichmentBatch(
                votes=[
                    VoteEnrichment(
                        ref=ref,
                        topics=["housing_rent", "housing_rent", "economy_finance"],
                        short_title=f"Kurz {ref}",
                        summary="Ein Satz.",
                        suggested_questions=[
                            "Was heißt das für mich?",
                            " ",
                            "Was heißt das für mich?",
                            "Wer war dagegen?",
                            "Was kostet das?",
                            "Eine vierte?",
                        ],
                    )
                    for ref in refs
                ]
            )
        if schema is DebateDraft:
            speaker, text = _first_speech(prompt)
            agenda_match = _AGENDA_RE.search(prompt)
            agenda = agenda_match.group(1) if agenda_match else ""
            return DebateDraft(
                topics=self.topics or ["housing_rent"],
                headline=f"Debatte: {agenda}",
                summary=f"Es ging um Antrag 21/123 zu {agenda}.",
                positions=[
                    PartyPositionDraft(party_id=p, position=f"Fordern Position {p}.")
                    for p in self._parties(prompt)
                    if p not in self.omit
                ],
                key_points=self.key_points or ["Eins.", "Zwei.", "Drei."],
                heat=self.heat,
                opening_quote=self.quote
                or OpeningQuoteDraft(speaker=speaker, quote=text),
                suggested_questions=["Was heißt das für mich?"],
            )
        if schema is PositionsDraft:
            return PositionsDraft(
                positions=[
                    PartyPositionDraft(party_id=p, position=f"Retry Position {p}.")
                    for p in self._parties(prompt)
                    if p not in self.retry_omit
                ]
            )
        if schema is PositionCheckBatch:
            return PositionCheckBatch(
                checks=[
                    PositionCheck(
                        ref=ref,
                        supported=not any(r in sentence for r in self.reject),
                        reason="geprüft",
                    )
                    for ref, _party, sentence in _CHECK_RE.findall(prompt)
                ]
            )
        raise AssertionError(f"unexpected schema {schema}")


def build(
    llm: FakeLLM,
    *,
    votes: Optional[list[dict]] = None,
    days: Optional[dict[date, SittingDay]] = None,
    out_of_time: Callable[[], bool] = lambda: False,
) -> list[FeedItem]:
    """Every item of the newest day, built from scratch."""
    builder = FeedBuilder(llm)
    try:
        [plan, *_] = plan_days(
            BUNDESTAG,
            [vote(1), vote(2)] if votes is None else votes,
            sittings() if days is None else days,
        )
        return build_day(
            builder,
            BUNDESTAG,
            plan,
            plan.debates,
            plan.votes,
            DISPLAY,
            now=NOW,
            out_of_time=out_of_time,
        )
    finally:
        builder.close()


def sample_items() -> list[FeedItem]:
    return build(FakeLLM())
