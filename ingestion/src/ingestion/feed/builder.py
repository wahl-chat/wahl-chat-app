# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Turn one parliament's window of corpus payloads into feed items.

The source decides the structure: every agenda item with speeches is one
debate item, every poll one vote item (see ``items.py``). The model only
writes the texts of one item at a time, and sees that debate whole.

LLM failure policy: a failed step never aborts the run. A vote falls back to
its source title under the ``other`` topic. A debate whose summary fails is
not built this run. A Fraktion that spoke but has no verified position after
one retry stays in the facts without a sentence. Every such item stores
``input_hash=None``, so the next run retries it.

Every text here is generated once and reused by every surface that shows it,
so all calls go to the publication roster (high reasoning) and each result
records which roster entry wrote it.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Coroutine, Optional, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from ingestion.feed.items import (
    canonical_content,
    debate_input_hash,
    debate_item_id,
    vote_input_hash,
    vote_item_id,
)
from ingestion.feed.models import (
    DebateFacts,
    DebateParty,
    DigestCitation,
    DigestProtocol,
    DigestQuote,
    DigestSpeaker,
    DigestVoteParty,
    FeedItem,
    LocalizedPosition,
    VoteFacts,
    edition_doc_id,
)
from ingestion.feed.parliaments import Parliament, PartyDisplay, party_display_for
from ingestion.feed.prompts import (
    DebateDraft,
    OpeningQuoteDraft,
    PartyPositionDraft,
    PositionsDraft,
    VoteEnrichment,
    VoteEnrichmentBatch,
    format_debate_prompt,
    format_positions_prompt,
    format_vote_prompt,
)
from ingestion.feed.reader import AgendaItem, SittingDay, Speech, parse_day
from ingestion.feed.topics import DigestTopic
from ingestion.feed.verify import verify_positions

logger = logging.getLogger(__name__)

# Small enough that each vote gets its share of the reasoning budget.
_VOTE_BATCH = 6
_VOTE_CONTEXT_CHARS = 1200
# A whole debate goes into the prompt. Only a debate longer than this (a
# budget week) has its speeches shortened, each by the same share, so every
# speech and every Fraktion is still in it.
_DEBATE_PROMPT_CHARS = 300_000
_MIN_SPEECH_CHARS = 1500
_CITATIONS_PER_DEBATE = 3
_DESCRIPTION_CHARS = 1500
# Typical Bundestag speaking pace; the debate length is an estimate from the
# protocol text, which carries no timestamps.
_WORDS_PER_MINUTE = 120
_SUGGESTED_QUESTIONS = 3
# A quote is shown whole on a card; longer sentences are dropped, not cut,
# because a cut quote is no longer verbatim.
_QUOTE_MAX_WORDS = 40
# The speeches in the prompt read "Name (party): …", and the model tends to
# copy the suffix into the speaker field.
_PARTY_SUFFIX_RE = re.compile(r"\s*\([^)]*\)\s*$")
_KEY_POINTS = 3
# The vote connector writes the embed text as "<label>\n\nThemen: …\n\nKontext: <intro>".
_CONTEXT_MARKER = "Kontext: "
# Speakers outside any Fraktion: listed with their speeches, but no position
# is required, since nobody speaks for them as a group.
NO_FRAKTION = frozenset({"fraktionslos", "fraktionslose", "unbekannt"})
# How many items are generated at once.
_CONCURRENCY = 4

# (messages, schema) -> (parsed schema instance, name of the model that wrote it).
StructuredOutputFn = Callable[
    [list[BaseMessage], type[BaseModel]], Coroutine[Any, Any, tuple[Any, str]]
]
T = TypeVar("T")


async def _default_structured_output(
    messages: list[BaseMessage], schema: type[BaseModel]
) -> tuple[Any, str]:
    from ingestion.feed.publication_llms import (  # noqa: PLC0415
        structured_output_from_publication_llms,
    )

    return await structured_output_from_publication_llms(messages, schema)


class FeedBuilder:
    """Runs the LLM steps on one process-wide event loop.

    The shared LLM clients cache connections bound to the loop they first ran
    on, so a per-call ``asyncio.run()`` would close that loop and break the
    next call on the same client.

    ``deadline`` (a ``time.monotonic()`` value) cuts every call still running
    when it passes, including the failover to further models, so a slow model
    cannot carry the run past the job's time cap.
    """

    def __init__(
        self,
        structured_output_fn: Optional[StructuredOutputFn] = None,
        *,
        deadline: Optional[float] = None,
        concurrency: int = _CONCURRENCY,
    ):
        self._fn = structured_output_fn or _default_structured_output
        self._runner = asyncio.Runner()
        self.deadline = deadline
        self.concurrency = concurrency

    def close(self) -> None:
        self._runner.close()

    def run(self, coroutine: Coroutine[Any, Any, T]) -> T:
        return self._runner.run(coroutine)

    def call(self, prompt: str, schema: type[BaseModel]) -> tuple[Any, str]:
        """One structured-output call: the parsed result and its model."""
        return self.run(self.acall(prompt, schema))

    async def acall(self, prompt: str, schema: type[BaseModel]) -> tuple[Any, str]:
        messages: list[BaseMessage] = [HumanMessage(content=prompt)]
        if self.deadline is None:
            return await self._fn(messages, schema)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("time budget spent")
        async with asyncio.timeout(remaining):
            return await self._fn(messages, schema)


# ---------------------------------------------------------------------------
# Source units: what the source says a day consists of
# ---------------------------------------------------------------------------


@dataclass
class DebateUnit:
    item_id: str
    agenda: AgendaItem
    protocols: list[DigestProtocol]
    input_hash: str

    @property
    def buildable(self) -> bool:
        return self.agenda.ordered


@dataclass
class VoteUnit:
    item_id: str
    payload: dict
    input_hash: str


@dataclass
class DayPlan:
    day: date
    edition_id: str
    protocols: list[DigestProtocol]
    debates: list[DebateUnit]
    votes: list[VoteUnit]

    @property
    def item_ids(self) -> list[str]:
        return [u.item_id for u in self.debates] + [u.item_id for u in self.votes]


def votes_by_day(vote_payloads: list[dict]) -> dict[date, list[dict]]:
    by_day: dict[date, list[dict]] = {}
    for payload in vote_payloads:
        day = parse_day(payload.get("publish_date"))
        if day is None or payload.get("external_id") is None:
            continue
        by_day.setdefault(day, []).append(payload)
    for payloads in by_day.values():
        payloads.sort(key=lambda p: int(p["external_id"]))
    return by_day


def _item_protocols(item: AgendaItem, sitting: SittingDay) -> list[DigestProtocol]:
    if item.session is None:
        return []
    protocol_id = f"{item.session[0]}/{item.session[1]}"
    return [
        DigestProtocol(protocol_id=p, pdf_url=u)
        for p, u in sitting.protocols
        if p == protocol_id
    ]


def plan_days(
    parliament: Parliament,
    vote_payloads: list[dict],
    sitting_days: dict[date, SittingDay],
) -> list[DayPlan]:
    """Every day with votes or a sitting, newest first, as source units."""
    by_day = votes_by_day(vote_payloads)
    plans: list[DayPlan] = []
    for day in sorted(set(by_day) | set(sitting_days), reverse=True):
        edition_id = edition_doc_id(parliament.id, day)
        sitting = sitting_days.get(day)
        debates: list[DebateUnit] = []
        for item in sitting.agenda_items if sitting else []:
            if item.session is None or not item.slug:
                # Procedural remarks outside any agenda item are no debate.
                logger.info(
                    "%s: %d speech(es) outside any agenda item left out",
                    edition_id,
                    len(item.speeches),
                )
                continue
            assert sitting is not None
            debates.append(
                DebateUnit(
                    item_id=debate_item_id(edition_id, item.session[1], item.slug),
                    agenda=item,
                    protocols=_item_protocols(item, sitting),
                    input_hash=debate_input_hash(item),
                )
            )
        votes = [
            VoteUnit(
                item_id=vote_item_id(edition_id, int(p["external_id"])),
                payload=p,
                input_hash=vote_input_hash(p),
            )
            for p in by_day.get(day, [])
        ]
        plans.append(
            DayPlan(
                day=day,
                edition_id=edition_id,
                protocols=[
                    DigestProtocol(protocol_id=p, pdf_url=u)
                    for p, u in (sitting.protocols if sitting else [])
                ],
                debates=debates,
                votes=votes,
            )
        )
    return plans


# ---------------------------------------------------------------------------
# Cleaning and grounding model output
# ---------------------------------------------------------------------------


def strip_refs(text: str, prefix: str) -> str:
    """Drop ids the model echoed from the prompt ("[S3]", "(S2, S4)") into a
    text; they mean nothing to a reader."""
    pattern = rf"\s*[\[(]?\b{prefix}\d+(?:\s*[,;/]\s*{prefix}\d+)*\b[\])]?"
    return re.sub(pattern, "", text).strip(" ,;:-")


def _normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def clean_questions(questions: list[str]) -> list[str]:
    cleaned = [q.strip() for q in questions if q.strip()]
    return list(dict.fromkeys(cleaned))[:_SUGGESTED_QUESTIONS]


def clean_key_points(points: list[str]) -> list[str]:
    """The card layout has room for exactly three bullets; any other count is
    dropped rather than padded or cut, so a bullet never goes missing silently."""
    cleaned = [p.strip() for p in points if p.strip()]
    return cleaned if len(cleaned) == _KEY_POINTS else []


def clean_topics(topics: list[DigestTopic]) -> list[DigestTopic]:
    """At most two distinct topics, primary first; ``other`` when none fit."""
    return list(dict.fromkeys(topics))[:2] or ["other"]


def clamp_heat(heat: Optional[int]) -> Optional[int]:
    return None if heat is None else max(1, min(5, heat))


def debate_minutes(speeches: list[Speech]) -> Optional[int]:
    words = sum(len(s.text.split()) for s in speeches)
    return max(1, round(words / _WORDS_PER_MINUTE)) if words else None


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip(" \"'„“”‚‘’»«").casefold()


class Fraktionen:
    """Party slugs mapped onto the Fraktion they sit in (CSU -> CDU)."""

    def __init__(self, aliases: dict[str, str]):
        self.aliases = aliases

    def of(self, party_id: str) -> str:
        party_id = party_id.strip().lower()
        return self.aliases.get(party_id, party_id)

    def speeches_by(self, speeches: list[Speech]) -> dict[str, list[Speech]]:
        """Each Fraktion's speeches, Fraktionen in order of their first speech."""
        found: dict[str, list[Speech]] = {}
        for speech in speeches:
            found.setdefault(self.of(speech.party_id), []).append(speech)
        return found


def debate_parties(
    speeches: list[Speech], display: dict[str, PartyDisplay], fraktionen: Fraktionen
) -> list[DebateParty]:
    """Every Fraktion that spoke, with each of its speakers once, linked to
    their first speech: straight from the source, never from the model."""
    parties: list[DebateParty] = []
    for party_id, party_speeches in fraktionen.speeches_by(speeches).items():
        first_by_name: dict[str, Speech] = {}
        for speech in party_speeches:
            if speech.speaker:
                first_by_name.setdefault(_normalize_name(speech.speaker), speech)
        party = party_display_for(party_id, display)
        parties.append(
            DebateParty(
                party_id=party_id,
                party_name=party.name,
                color=party.color,
                speakers=[
                    DigestSpeaker(
                        name=s.speaker,
                        url=s.protocol_page_url or s.pdf_url,
                        video_url=s.video_uri,
                        video_link=s.citation_url if s.video_uri else None,
                    )
                    for s in first_by_name.values()
                ],
            )
        )
    return parties


def ground_positions(
    drafted: list[PartyPositionDraft], spoke: set[str], fraktionen: Fraktionen
) -> dict[str, str]:
    """Position text per Fraktion, kept only for Fraktionen that spoke. A
    second entry for the same Fraktion (CSU next to CDU) is dropped: the first
    text stands."""
    positions: dict[str, str] = {}
    for position in drafted:
        party_id = fraktionen.of(position.party_id)
        text = position.position.strip()
        if party_id in spoke and text and party_id not in positions:
            positions[party_id] = text
    return positions


def ground_quote(
    drafted: Optional[OpeningQuoteDraft],
    speeches: list[Speech],
    display: dict[str, PartyDisplay],
    fraktionen: Fraktionen,
) -> Optional[DigestQuote]:
    """Keep the quote only if it appears verbatim in that speaker's speech
    here, so a paraphrase is never presented as a citation."""
    if drafted is None:
        return None
    quote = _normalize_text(drafted.quote)
    speaker = _normalize_name(_PARTY_SUFFIX_RE.sub("", drafted.speaker))
    if not quote or len(quote.split()) > _QUOTE_MAX_WORDS:
        return None
    for speech in speeches:
        if _normalize_name(speech.speaker or "") != speaker:
            continue
        if quote not in _normalize_text(speech.text):
            continue
        party_id = fraktionen.of(speech.party_id)
        return DigestQuote(
            text=" ".join(drafted.quote.split()).strip(" \"'„“”‚‘’»«"),
            speaker=speech.speaker,
            party_id=party_id,
            party_name=party_display_for(party_id, display).name,
        )
    return None


def opening_party(speeches: list[Speech], fraktionen: Fraktionen) -> Optional[str]:
    """The Fraktion of the debate's first speaker, which is usually the one
    that brought the item onto the agenda."""
    if not speeches or not speeches[0].party_id:
        return None
    return fraktionen.of(speeches[0].party_id)


def citations(
    speeches: list[Speech], label: str, display: dict[str, PartyDisplay]
) -> list[DigestCitation]:
    """The debate's first speeches, each linked to its source."""
    found: list[DigestCitation] = []
    seen: set[str] = set()
    for speech in speeches:
        if not speech.citation_url or speech.citation_url in seen:
            continue
        seen.add(speech.citation_url)
        # The logo is the speaker's own party (CSU, not the Union).
        party = party_display_for(speech.party_id, display)
        found.append(
            DigestCitation(
                title=speech.citation_title or speech.speaker or label,
                url=speech.citation_url,
                speaker=speech.speaker or None,
                party_id=speech.party_id,
                party_name=party.name,
                color=party.color,
                video_url=speech.video_uri,
            )
        )
        if len(found) == _CITATIONS_PER_DEBATE:
            break
    return found


def speeches_block(speeches: list[Speech], limit: int = _DEBATE_PROMPT_CHARS) -> str:
    """The speeches as "- Name (party): text", in order. Over ``limit``, each
    is shortened by the same share, never below a floor and never dropped."""
    total = sum(len(s.text) for s in speeches) or 1
    share = min(1.0, limit / total)
    lines = []
    for speech in speeches:
        keep = len(speech.text)
        if share < 1.0:
            keep = max(_MIN_SPEECH_CHARS, int(keep * share))
        text = " ".join(speech.text[:keep].split())
        lines.append(f"- {speech.speaker or 'Unbekannt'} ({speech.party_id}): {text}")
    return "\n".join(lines)


def vote_description(text: str) -> Optional[str]:
    """The poll's intro from the vote chunk text, cut at a sentence end."""
    _, marker, context = text.partition(_CONTEXT_MARKER)
    context = context.strip()
    if not marker or not context:
        return None
    if len(context) <= _DESCRIPTION_CHARS:
        return context
    cut = context[:_DESCRIPTION_CHARS]
    sentence_end = cut.rfind(". ")
    return (cut[: sentence_end + 1] if sentence_end > 0 else cut.rstrip()) + " …"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _item_base(parliament: Parliament, edition_id: str, day: date) -> dict[str, Any]:
    return {
        "edition_id": edition_id,
        "parliament": parliament.id,
        "parliament_name": parliament.name,
        "region": parliament.region,
        "date": day,
        "rank": 0,
    }


async def _positions_for(
    builder: FeedBuilder,
    parliament: Parliament,
    agenda: AgendaItem,
    wanted: list[str],
    drafted: list[PartyPositionDraft],
    by_party: dict[str, list[Speech]],
    fraktionen: Fraktionen,
) -> dict[str, str]:
    """The drafted positions of ``wanted`` that the speeches support."""
    grounded = ground_positions(drafted, set(wanted), fraktionen)
    return await verify_positions(
        builder, parliament.name, agenda.label, grounded, by_party
    )


async def build_debate(
    builder: FeedBuilder,
    parliament: Parliament,
    plan: DayPlan,
    unit: DebateUnit,
    display: dict[str, PartyDisplay],
    generated_at: datetime,
) -> Optional[FeedItem]:
    """One debate item, or None when its summary could not be written."""
    agenda = unit.agenda
    speeches = agenda.speeches
    fraktionen = Fraktionen(dict(parliament.party_aliases))
    by_party = fraktionen.speeches_by(speeches)
    required = [p for p in by_party if p not in NO_FRAKTION]
    try:
        draft, model = await builder.acall(
            format_debate_prompt(
                parliament.name,
                plan.day.strftime("%d.%m.%Y"),
                agenda.label,
                ", ".join(by_party),
                speeches_block(speeches),
            ),
            DebateDraft,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Debate %s failed: %s", unit.item_id, exc)
        return None

    positions = await _positions_for(
        builder,
        parliament,
        agenda,
        list(by_party),
        draft.positions,
        by_party,
        fraktionen,
    )
    missing = [p for p in required if p not in positions]
    if missing:
        logger.info("%s: retrying positions for %s", unit.item_id, missing)
        positions.update(
            await _retry_positions(
                builder, parliament, agenda, missing, by_party, fraktionen
            )
        )
        missing = [p for p in required if p not in positions]
    if missing:
        logger.warning(
            "%s: no verified position for %s; listed without one",
            unit.item_id,
            missing,
        )

    parties = debate_parties(speeches, display, fraktionen)
    return FeedItem(
        id=unit.item_id,
        kind="debate",
        **_item_base(parliament, plan.edition_id, plan.day),
        topics=clean_topics(draft.topics),
        debate=DebateFacts(
            protocols=unit.protocols,
            agenda_item=agenda.label,
            citations=citations(speeches, agenda.label, display),
            parties=parties,
            video_url=agenda.video_url,
            heat=clamp_heat(draft.heat),
            debate_minutes=debate_minutes(speeches),
            opened_by=opening_party(speeches, fraktionen),
            opening_quote=ground_quote(
                draft.opening_quote, speeches, display, fraktionen
            ),
        ),
        content=canonical_content(
            headline=draft.headline.strip(),
            teaser=draft.summary.strip(),
            key_points=clean_key_points(draft.key_points),
            positions=[
                LocalizedPosition(party_id=p.party_id, text=positions[p.party_id])
                for p in parties
                if p.party_id in positions
            ],
            suggested_questions=clean_questions(draft.suggested_questions),
            generated_by=model,
            generated_at=generated_at,
        ),
        input_hash=None if missing else unit.input_hash,
        generated_at=generated_at,
    )


async def _retry_positions(
    builder: FeedBuilder,
    parliament: Parliament,
    agenda: AgendaItem,
    missing: list[str],
    by_party: dict[str, list[Speech]],
    fraktionen: Fraktionen,
) -> dict[str, str]:
    """One more attempt for the Fraktionen without a verified position, from
    their own speeches only."""
    speeches = [s for p in missing for s in by_party[p]]
    try:
        retried, _ = await builder.acall(
            format_positions_prompt(
                parliament.name,
                agenda.label,
                ", ".join(missing),
                speeches_block(speeches),
            ),
            PositionsDraft,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Position retry failed for %s: %s", agenda.key, exc)
        return {}
    return await _positions_for(
        builder, parliament, agenda, missing, retried.positions, by_party, fraktionen
    )


@dataclass
class VoteText:
    title: str
    short_title: str
    summary: Optional[str]
    topics: list[DigestTopic]
    suggested_questions: list[str]
    generated_by: Optional[str] = None


async def enrich_votes(
    builder: FeedBuilder, parliament: Parliament, payloads: list[dict]
) -> tuple[dict[int, Optional[VoteEnrichment]], Optional[str]]:
    """The model's texts per poll id (None where it gave none), and the model."""
    found: dict[int, Optional[VoteEnrichment]] = {}
    refs = {f"V{i + 1}": p for i, p in enumerate(payloads)}
    block = "\n\n".join(
        f"[{ref}] {str(p.get('text') or '')[:_VOTE_CONTEXT_CHARS]}"
        for ref, p in refs.items()
    )
    try:
        result, model = await builder.acall(
            format_vote_prompt(parliament.name, block), VoteEnrichmentBatch
        )
        enriched = {v.ref: v for v in result.votes if v.ref in refs}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Vote enrichment failed for %s: %s", parliament.id, exc)
        enriched, model = {}, None
    for ref, payload in refs.items():
        found[int(payload["external_id"])] = enriched.get(ref)
    return found, model


def vote_item(
    parliament: Parliament,
    plan: DayPlan,
    unit: VoteUnit,
    enrichment: Optional[VoteEnrichment],
    model: Optional[str],
    display: dict[str, PartyDisplay],
    generated_at: datetime,
) -> FeedItem:
    payload = unit.payload
    meta = payload.get("meta") or {}
    title = str(payload.get("citation_title") or "Abstimmung")
    parties = []
    for result in meta.get("vote_results") or []:
        party = party_display_for(str(result.get("party_id")), display)
        parties.append(
            DigestVoteParty(
                party_id=str(result.get("party_id")),
                name=party.name,
                color=party.color,
                yes=int(result.get("yes") or 0),
                no=int(result.get("no") or 0),
                abstain=int(result.get("abstain") or 0),
                no_show=int(result.get("no_show") or 0),
            )
        )
    if enrichment is None:
        text = VoteText(title, title, None, ["other"], [])
    else:
        text = VoteText(
            title=title,
            short_title=enrichment.short_title.strip() or title,
            summary=enrichment.summary.strip() or None,
            topics=clean_topics(enrichment.topics),
            suggested_questions=clean_questions(enrichment.suggested_questions),
            generated_by=model,
        )
    return FeedItem(
        id=unit.item_id,
        kind="vote",
        **_item_base(parliament, plan.edition_id, plan.day),
        topics=text.topics,
        vote=VoteFacts(
            poll_id=int(payload["external_id"]),
            official_title=title,
            outcome=meta.get("motion_outcome"),
            citation_url=payload.get("citation_url"),
            description=vote_description(str(payload.get("text") or "")),
            parties=parties,
        ),
        content=canonical_content(
            headline=text.short_title,
            teaser=text.summary,
            key_points=[],
            positions=[],
            suggested_questions=text.suggested_questions,
            generated_by=text.generated_by,
            generated_at=generated_at,
        ),
        input_hash=None if enrichment is None else unit.input_hash,
        generated_at=generated_at,
    )


async def _bounded(
    semaphore: asyncio.Semaphore,
    out_of_time: Callable[[], bool],
    make: Callable[[], Awaitable[T]],
) -> Optional[T]:
    """Start the work only while there is time left; an item never started
    is built by the next run."""
    async with semaphore:
        if out_of_time():
            return None
        return await make()


async def _build_day(
    builder: FeedBuilder,
    parliament: Parliament,
    plan: DayPlan,
    debates: list[DebateUnit],
    votes: list[VoteUnit],
    display: dict[str, PartyDisplay],
    generated_at: datetime,
    out_of_time: Callable[[], bool],
) -> list[FeedItem]:
    semaphore = asyncio.Semaphore(builder.concurrency)

    def debate_job(unit: DebateUnit) -> Callable[[], Awaitable[Optional[FeedItem]]]:
        return lambda: build_debate(
            builder, parliament, plan, unit, display, generated_at
        )

    def vote_job(batch: list[VoteUnit]) -> Callable[[], Awaitable[list[FeedItem]]]:
        async def run() -> list[FeedItem]:
            enriched, model = await enrich_votes(
                builder, parliament, [u.payload for u in batch]
            )
            return [
                vote_item(
                    parliament,
                    plan,
                    unit,
                    enriched.get(int(unit.payload["external_id"])),
                    model,
                    display,
                    generated_at,
                )
                for unit in batch
            ]

        return run

    vote_batches = [
        votes[start : start + _VOTE_BATCH]
        for start in range(0, len(votes), _VOTE_BATCH)
    ]
    debate_results, vote_results = await asyncio.gather(
        asyncio.gather(
            *(_bounded(semaphore, out_of_time, debate_job(u)) for u in debates)
        ),
        asyncio.gather(
            *(_bounded(semaphore, out_of_time, vote_job(b)) for b in vote_batches)
        ),
    )
    built = [item for item in debate_results if item is not None]
    for batch in vote_results:
        built.extend(batch or [])
    return built


def build_day(
    builder: FeedBuilder,
    parliament: Parliament,
    plan: DayPlan,
    debates: list[DebateUnit],
    votes: list[VoteUnit],
    display: dict[str, PartyDisplay],
    *,
    now: Optional[datetime] = None,
    out_of_time: Callable[[], bool] = lambda: False,
) -> list[FeedItem]:
    """Generate the given units of one day, concurrently; returns what was
    built. A unit missing from the result was not built (failed, or the time
    budget ran out before it started)."""
    return builder.run(
        _build_day(
            builder,
            parliament,
            plan,
            [u for u in debates if u.buildable],
            votes,
            display,
            now or datetime.now(timezone.utc),
            out_of_time,
        )
    )
