# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The agent's tools as plain async functions over ``GenericChatDeps``.

Each tool registers the documents it returns in the turn's source registry and
hands them to the model under their citation number.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, cast
from zoneinfo import ZoneInfo

from langchain_core.documents import Document
from pydantic import ValidationError
from pydantic_ai.framing import register_tag, wrap
from qdrant_client.models import DatetimeRange

from src.generic_chat import web_search as web
from src.generic_chat.schemas import (
    AnchorContext,
    Anchor,
    DebateResult,
    FeedItemsResult,
    FeedItemView,
    GenericChatDeps,
    GetProcessInput,
    ListFeedItemsInput,
    NumberedDocument,
    ProcedureRef,
    SearchInput,
    SearchSourceType,
    ToolResult,
    WebSearchInput,
)
from src.retrieve import embed_query, fetch_payloads, retrieve
from src.services.chat.service import (
    _append_document_source,
    _mk_manifesto_docs,
    _mk_speech_docs,
)
from src.services.firebase_service import aget_feed_item, aget_feed_items
from src.services import procedure_service
from src.services.procedure_service import aprocedures_for_chunks
from wahlchat_common.legislature_config import (
    LEGISLATURE_CONFIG,
    LegislatureConfig,
    term_window_for_context,
)

logger = logging.getLogger(__name__)

BERLIN = ZoneInfo("Europe/Berlin")

# The feed's parliament ids by the context's most specific region.
PARLIAMENT_BY_REGION: dict[str, str] = {
    "DE": "bundestag",
    "DE-ST": "landtag_st",
    "DE-BW": "landtag_bw",
}

_SEARCH_LIMITS: dict[SearchSourceType, int] = {
    "vote_record": 5,
    "parliamentary_speech": 4,
    "party_manifesto": 4,
}
# Ranking by time; numbers provisional until measured on the eval set.
# Votes and speeches: "recent" by age; manifestos: by term (a manifesto stays
# the programme until the next election).
_RECENT_DAYS = 730
_RECENT_MIN_SCORE = 0.5
_RECENT_HALFLIFE_DAYS = 3650  # mild: two years old weighs ~0.87
_EARLIER_MIN_SCORE = 0.6
_EARLIER_HALFLIFE_DAYS = 1826
_EARLIER_LIMITS: dict[SearchSourceType, int] = {
    "vote_record": 2,
    "parliamentary_speech": 1,
    "party_manifesto": 2,
}
# Manifestos are dated election day, before the term starts.
_MANIFESTO_LEAD_DAYS = 60
_SEARCH_TEXT_CHARS = 1500
_SPEECH_TEXT_CHARS = 2500
_MAX_DEBATE_SPEECHES = 12
_MAX_FEED_WINDOW_DAYS = 31
_MAX_FEED_ITEMS = 40
# A debate on a poll's Drucksache is usually the same day, at most a week earlier.
_DEBATE_LOOKBACK_DAYS = 7
_DEBATE_NOTE = (
    "The speeches above are from the debate on this vote ({date}): the reasons"
    " given for it."
)
# Votes in the same procedure besides the one asked about, e.g. on amendments.
_OTHER_VOTES = 3
# The vote's own debate is missing, the law's earlier readings are not.
_LAW_DEBATE_NOTE = (
    "No debate on the day of this vote is in our data. The speeches above are"
    " from the readings of the law it belongs to ({dates}): reasons given for"
    " the law, made before this vote; say when they were made."
)
# Neutral on why: some votes have no debate, others' speeches arrive days later.
_NO_DEBATE_NOTE = (
    "No debate linked to this vote was found in our data. Speeches found"
    " elsewhere are statements made on other occasions, not reasons given for"
    " this vote."
)

_STANCE = {
    "agree": "mostly yes",
    "disagree": "mostly no",
    "neutral": "mostly abstained / split",
    "absent": "mostly did not vote",
}

_WEB_SNIPPET = register_tag("web_snippet")
_PROCEDURES_PER_DOCUMENT = 2


def _clip(text: Optional[str], limit: int) -> str:
    normalized = " ".join((text or "").split())
    return normalized if len(normalized) <= limit else normalized[:limit] + " …"


def _meta(payload: dict) -> dict:
    meta = payload.get("meta")
    return meta if isinstance(meta, dict) else {}


def _publish_range(since: Optional[date], until: Optional[date]) -> Optional[DatetimeRange]:
    if since is None and until is None:
        return None
    return DatetimeRange(
        gte=datetime.combine(since, time.min, timezone.utc) if since else None,
        lte=datetime.combine(until, time.max, timezone.utc) if until else None,
    )


def parliament_for(deps: GenericChatDeps) -> Optional[str]:
    region = deps.context.region_path[-1] if deps.context.region_path else "DE"
    return PARLIAMENT_BY_REGION.get(region)


# ---------------------------------------------------------------------------
# Source registration: the sources_ready entry + the model-facing document
# ---------------------------------------------------------------------------


def _document_entry(doc: Document, party_id: Optional[str]) -> dict:
    entries: list[dict] = []
    _append_document_source(entries, [], doc, party_id=party_id)
    return entries[0]


def _register_vote(deps: GenericChatDeps, payload: dict) -> NumberedDocument:
    title = payload.get("citation_title")
    number = deps.sources.register(
        {
            "source": title,
            "page": 1,
            "document_publish_date": payload.get("publish_date"),
            "url": payload.get("citation_url"),
            "source_document": title,
            "source_type": "vote_record",
            "region": payload.get("region"),
        }
    )
    meta = _meta(payload)
    lines = [f"Outcome: {meta.get('motion_outcome') or 'unknown'}"]
    for result in meta.get("vote_results") or []:
        if not isinstance(result, dict):
            continue
        lines.append(
            f"{deps.party_name(result.get('party_id'))}: yes {result.get('yes', 0)}, "
            f"no {result.get('no', 0)}, abstain {result.get('abstain', 0)}, "
            f"did not vote {result.get('no_show', 0)} "
            f"({_STANCE.get(str(result.get('stance')), 'unknown')})"
        )
    if payload.get("text"):
        lines.append(_clip(payload.get("text"), _SEARCH_TEXT_CHARS))
    poll_id = payload.get("external_id")
    return NumberedDocument(
        id=number,
        source_type="vote_record",
        title=title,
        date=payload.get("publish_date"),
        poll_id=int(str(poll_id)) if str(poll_id or "").isdigit() else None,
        text="\n".join(lines),
    )


def _register_speech(
    deps: GenericChatDeps, payload: dict, query: str, text: str
) -> NumberedDocument:
    doc = _mk_speech_docs([payload], query)[0]
    number = deps.sources.register(_document_entry(doc, payload.get("party_id")))
    speaker = _meta(payload).get("speaker_name")
    party = deps.party_name(payload.get("party_id"))
    return NumberedDocument(
        id=number,
        source_type="parliamentary_speech",
        title=payload.get("citation_title"),
        date=payload.get("publish_date"),
        party=f"{speaker} ({party})" if speaker else party,
        text=text,
    )


def _register_manifesto(deps: GenericChatDeps, payload: dict) -> NumberedDocument:
    doc = _mk_manifesto_docs([payload])[0]
    number = deps.sources.register(_document_entry(doc, payload.get("party_id")))
    return NumberedDocument(
        id=number,
        source_type="party_manifesto",
        title=payload.get("citation_title"),
        date=payload.get("publish_date"),
        party=deps.party_name(payload.get("party_id")),
        text=_clip(payload.get("text"), _SEARCH_TEXT_CHARS),
    )


def _register_payload(
    deps: GenericChatDeps, payload: dict, query: str
) -> NumberedDocument:
    source_type = payload.get("source_type")
    if source_type == "vote_record":
        return _register_vote(deps, payload)
    if source_type == "parliamentary_speech":
        return _register_speech(
            deps, payload, query, _clip(payload.get("text"), _SEARCH_TEXT_CHARS)
        )
    return _register_manifesto(deps, payload)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def _today() -> date:
    return datetime.now(BERLIN).date()


def federal_terms() -> list[LegislatureConfig]:
    """Bundestag terms, oldest first."""
    rows = [c for c in LEGISLATURE_CONFIG.values() if c.region == "DE" and c.wahlperiode]
    return sorted(rows, key=lambda c: c.date_from)


def _wahlperiode(day: Optional[date]) -> Optional[int]:
    if day is None:
        return None
    for term in federal_terms():
        if term.date_from <= day.isoformat() <= (term.date_to or "9999"):
            return term.wahlperiode
    return None


def _day(payload: dict) -> Optional[date]:
    raw = payload.get("publish_date")
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


def _decayed(hits: list[tuple[dict, float]], anchor: date, halflife: int) -> list[dict]:
    """Highest first after halving the score every ``halflife`` days before ``anchor``."""

    def weight(hit: tuple[dict, float]) -> float:
        day = _day(hit[0])
        age = max(0, (anchor - day).days) if day else 0
        return max(hit[1], 0.0) * 0.5 ** (age / halflife)

    return [payload for payload, _ in sorted(hits, key=weight, reverse=True)]


def _cutoff(deps: GenericChatDeps, source_type: SearchSourceType, today: date) -> date:
    """First day that counts as recent."""
    if source_type == "party_manifesto":
        window = term_window_for_context(
            deps.context.region_path, deps.context.legislature_period_id
        )
        if window is not None:
            return window[0].date() - timedelta(days=_MANIFESTO_LEAD_DAYS)
    return today - timedelta(days=_RECENT_DAYS)


def _named_term(args: SearchInput) -> Optional[LegislatureConfig]:
    if args.wahlperiode is None:
        return None
    term = next((t for t in federal_terms() if t.wahlperiode == args.wahlperiode), None)
    if term is None:
        raise ValueError(f"Unknown Wahlperiode {args.wahlperiode}.")
    return term


def _explicit_window(
    args: SearchInput, term: Optional[LegislatureConfig], source_type: SearchSourceType
) -> Optional[DatetimeRange]:
    since, until = args.since, args.until
    if term is not None:
        # A term's manifestos are dated before it starts, like the term window.
        lead = timedelta(days=_MANIFESTO_LEAD_DAYS if source_type == "party_manifesto" else 0)
        start = date.fromisoformat(term.date_from) - lead
        end = date.fromisoformat(term.date_to) - lead if term.date_to else None
        since = max(since, start) if since else start
        until = min(until, end) if until and end else (until or end)
    return _publish_range(since, until)


def _bound(day: date) -> datetime:
    return datetime.combine(day, time.min, timezone.utc)


async def _search_type(
    deps: GenericChatDeps,
    args: SearchInput,
    source_type: SearchSourceType,
    vector: list[float],
    term: Optional[LegislatureConfig],
    today: date,
    party_id: Optional[str],
    share: int,
) -> tuple[list[dict], list[dict]]:
    """(recent, earlier) payloads; an explicit window searches only that window.
    ``share`` parties split the type's limits."""
    # Votes belong to no single party: membership via party_ids, not the tenant key.
    party_filter: dict[str, str] = {}
    if party_id:
        key = "party_ids_contains" if source_type == "vote_record" else "party_id"
        party_filter[key] = party_id

    async def fetch(
        publish_range: DatetimeRange, limit: int, min_score: float
    ) -> list[tuple[dict, float]]:
        return cast(
            list[tuple[dict, float]],
            await retrieve(
                args.query,
                source_type=source_type,
                region_path=deps.context.region_path,
                level=deps.context.level,
                limit=limit,
                publish_range=publish_range,
                query_vector=vector,
                score_threshold=min_score,
                with_scores=True,
                **party_filter,  # type: ignore[arg-type]
            ),
        )

    limit = _split(_SEARCH_LIMITS[source_type], share)
    window = _explicit_window(args, term, source_type)
    if window is not None:
        hits = await fetch(window, limit, _RECENT_MIN_SCORE)
        return _decayed(hits, today, _RECENT_HALFLIFE_DAYS), []
    cutoff = _cutoff(deps, source_type, today)
    cap = _split(_EARLIER_LIMITS[source_type], share)
    recent, earlier = await asyncio.gather(
        fetch(DatetimeRange(gte=_bound(cutoff)), limit, _RECENT_MIN_SCORE),
        # Over-fetch so the decay picks among more than the raw top few.
        fetch(DatetimeRange(lt=_bound(cutoff)), max(cap * 10, 20), _EARLIER_MIN_SCORE),
    )
    return (
        _decayed(recent, today, _RECENT_HALFLIFE_DAYS),
        _decayed(earlier, cutoff, _EARLIER_HALFLIFE_DAYS)[:cap],
    )


def _split(limit: int, share: int) -> int:
    return max(1, -(-limit // share))


def _party_scopes(
    deps: GenericChatDeps, args: SearchInput, source_type: SearchSourceType
) -> list[Optional[str]]:
    """The party filters one source type is searched with: an unscoped search
    in a focused chat runs once per focus party."""
    # A vote carries every party's tally, so the focus does not split it.
    if args.party_id or not deps.focus or source_type == "vote_record":
        return [args.party_id]
    return [party.party_id for party in deps.focus]


async def search(deps: GenericChatDeps, args: SearchInput) -> ToolResult:
    try:
        term = _named_term(args)
    except ValueError as exc:
        return ToolResult(note=str(exc))
    source_types = list(dict.fromkeys(args.source_types or _SEARCH_LIMITS))
    jobs = [
        (source_type, party_id, len(scopes))
        for source_type in source_types
        for scopes in [_party_scopes(deps, args, source_type)]
        for party_id in scopes
    ]
    today = _today()
    vector = await embed_query(args.query)
    buckets = await asyncio.gather(
        *(
            _search_type(deps, args, t, vector, term, today, party_id, share)
            for t, party_id, share in jobs
        ),
        return_exceptions=True,
    )
    recent: list[dict] = []
    earlier: list[dict] = []
    for (source_type, _, _), bucket in zip(jobs, buckets):
        if isinstance(bucket, BaseException):
            logger.warning("search: %s retrieval failed: %s", source_type, bucket)
            continue
        recent += bucket[0]
        earlier += bucket[1]
    scoped = await _scoped_hits(deps, args, vector, source_types)
    inside = {str(p.get("chunk_key")) for p in scoped}
    recent = [p for p in recent if str(p.get("chunk_key")) not in inside]
    earlier = [p for p in earlier if str(p.get("chunk_key")) not in inside]
    procedures = await _procedures_of(scoped + recent + earlier)
    documents: list[NumberedDocument] = []
    for payload in scoped + recent + earlier:
        day = _day(payload)
        source_type = cast(SearchSourceType, payload.get("source_type"))
        is_recent = day is None or day >= _cutoff(deps, source_type, today)
        documents.append(
            _register_payload(deps, payload, args.query).model_copy(
                update={
                    "wahlperiode": _wahlperiode(day),
                    "period": "recent" if is_recent else "earlier",
                    "procedures": procedures.get(str(payload.get("chunk_key"))) or None,
                    "tier": (
                        None if not deps.scope
                        else "this_procedure" if str(payload.get("chunk_key")) in inside
                        else "context"
                    ),
                }
            )
        )
    return ToolResult(
        documents=documents,
        note=None if documents else "No matching sources in the corpus.",
    )


# Inside the procedures in scope: their speeches and votes, by party.
_SCOPED_TYPES: tuple[SearchSourceType, ...] = ("parliamentary_speech", "vote_record")
_SCOPED_LIMIT = 4
_SCOPED_PROCEDURES = 2


async def _scoped_hits(
    deps: GenericChatDeps,
    args: SearchInput,
    vector: list[float],
    source_types: list[SearchSourceType],
) -> list[dict]:
    """The search inside the procedures the chat is about; empty without a
    scope or for a question about another period."""
    if not deps.scope or args.since or args.until or args.wahlperiode:
        return []
    jobs = [
        (source_type, vorgang_id, party_id)
        for source_type in source_types if source_type in _SCOPED_TYPES
        for vorgang_id in deps.scope[:_SCOPED_PROCEDURES]
        for party_id in _party_scopes(deps, args, source_type)
    ]

    async def one(source_type: SearchSourceType, vorgang_id: str, party_id: Optional[str]) -> list[dict]:
        party = (
            {}
            if not party_id
            else {"party_ids_contains" if source_type == "vote_record" else "party_id": party_id}
        )
        return cast(
            list[dict],
            await retrieve(
                args.query, source_type=source_type, vorgang_id=vorgang_id,
                limit=_SCOPED_LIMIT, query_vector=vector, **party,  # type: ignore[arg-type]
            ),
        )

    results = await asyncio.gather(*(one(*job) for job in jobs), return_exceptions=True)
    seen: set[str] = set()
    hits: list[dict] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("search: scoped retrieval failed: %s", result)
            continue
        for payload in result:
            key = str(payload.get("chunk_key"))
            if key not in seen:
                seen.add(key)
                hits.append(payload)
    return hits


async def _procedures_of(payloads: list[dict]) -> dict[str, list[ProcedureRef]]:
    """chunk_key → the procedures of a vote or speech; empty when the lookup fails."""
    linked = [p for p in payloads if p.get("vorgang_ids")]
    if not linked:
        return {}
    try:
        by_chunk = await aprocedures_for_chunks(linked)
    except Exception as exc:  # noqa: BLE001 (the offer is optional)
        logger.warning("search: procedure lookup failed: %s", exc)
        return {}
    return {
        key: [
            ProcedureRef(
                vorgang_id=s.vorgang_id,
                title=s.titel,
                latest_stage=(
                    f"{s.latest_stage} ({s.latest_stage_on.isoformat()})"
                    if s.latest_stage and s.latest_stage_on
                    else s.latest_stage
                ),
            )
            for s in summaries[:_PROCEDURES_PER_DOCUMENT]
        ]
        for key, summaries in by_chunk.items()
    }


# ---------------------------------------------------------------------------
# feed items, get_debate, get_vote
# ---------------------------------------------------------------------------


async def load_feed_item(feed_item_id: str) -> Optional[FeedItemView]:
    raw = await aget_feed_item(feed_item_id)
    if raw is None:
        return None
    try:
        item = FeedItemView.model_validate(raw)
    except ValidationError as exc:
        logger.warning("feed item %s does not validate: %s", feed_item_id, exc)
        return None
    return item if item.status == "published" else None


async def _speeches_by_ids(speech_ids: list[str]) -> list[tuple[dict, str]]:
    """(first chunk payload, joined text) per speech, in ``speech_ids`` order."""
    wanted = speech_ids[:_MAX_DEBATE_SPEECHES]
    chunks = await fetch_payloads(
        "parliamentary_speech", source_item_ids=wanted, limit=len(wanted) * 12
    )
    by_speech: dict[str, list[dict]] = defaultdict(list)
    for chunk in chunks:
        by_speech[str(chunk.get("source_item_id"))].append(chunk)
    speeches: list[tuple[dict, str]] = []
    for speech_id in wanted:
        parts = sorted(by_speech.get(speech_id, []), key=lambda c: c.get("chunk_index") or 0)
        if parts:
            text = " ".join(str(p.get("text") or "") for p in parts)
            speeches.append((parts[0], _clip(text, _SPEECH_TEXT_CHARS)))
    return speeches


async def _speeches_by_search(
    deps: GenericChatDeps, item: FeedItemView
) -> list[tuple[dict, str]]:
    """Fallback for items stored without ``speech_ids``: the day's speeches
    closest to the agenda topic."""
    day = date.fromisoformat(item.date[:10])
    query = f"{item.debate.agenda_item if item.debate else ''} {item.headline('de')}"
    payloads = cast(
        list[dict],
        await retrieve(
            query.strip(),
            source_type="parliamentary_speech",
            region_path=deps.context.region_path,
            limit=8,
            publish_range=_publish_range(day, day),
        ),
    )
    return [(p, _clip(p.get("text"), _SPEECH_TEXT_CHARS)) for p in payloads]


async def _debate_documents(
    deps: GenericChatDeps, item: FeedItemView
) -> tuple[list[NumberedDocument], Optional[str]]:
    speech_ids = item.debate.speech_ids if item.debate else None
    if speech_ids:
        speeches = await _speeches_by_ids(speech_ids)
        note = None
    else:
        speeches = await _speeches_by_search(deps, item)
        note = "Speeches matched by date and topic; the list may be incomplete."
    query = item.debate.agenda_item if item.debate else item.headline("de")
    documents = [
        _register_speech(deps, p, query, text).model_copy(update={"tier": "this_item"})
        for p, text in speeches
    ]
    return documents, note if documents else "No speeches found for this debate."


async def get_debate(deps: GenericChatDeps, feed_item_id: str) -> DebateResult:
    item = await load_feed_item(feed_item_id)
    if item is None:
        return DebateResult(note=f"Feed item {feed_item_id} not found.")
    if item.kind == "vote" and item.vote is not None:
        return await get_vote(deps, item.vote.poll_id)
    documents, note = await _debate_documents(deps, item)
    deps.add_scope(item.procedure_ids)
    deps.settle(Anchor(feed_item_id=item.id))
    return DebateResult(
        documents=documents, note=note, item=item.summary(deps.language)
    )


async def _debate_for_vote(
    parliament: str, vote_item: FeedItemView
) -> Optional[FeedItemView]:
    drucksachen = set(vote_item.vote.drucksachen or []) if vote_item.vote else set()
    if not drucksachen:
        return None
    day = date.fromisoformat(vote_item.date[:10])
    raws = await aget_feed_items(
        parliament, day - timedelta(days=_DEBATE_LOOKBACK_DAYS), day, kind="debate"
    )
    for raw in raws:
        try:
            debate = FeedItemView.model_validate(raw)
        except ValidationError:
            continue
        if debate.debate and drucksachen & set(debate.debate.drucksachen or []):
            return debate
    return None


async def get_vote(
    deps: GenericChatDeps, poll_id: int, party_ids: Optional[list[str]] = None
) -> DebateResult:
    payloads = await fetch_payloads("vote_record", external_id=poll_id, limit=8)
    if not payloads:
        return DebateResult(note=f"No vote record found for poll {poll_id}.")
    payload = min(payloads, key=lambda p: p.get("chunk_index") or 0)
    documents = [_register_vote(deps, payload)]
    note: Optional[str] = None

    parliament = PARLIAMENT_BY_REGION.get(str(payload.get("region") or ""))
    vote_item: Optional[FeedItemView] = None
    if parliament and payload.get("publish_date"):
        day = str(payload["publish_date"])[:10]
        vote_item = await load_feed_item(f"{parliament}_{day}_v{poll_id}")
    debate = None
    if parliament and vote_item is not None:
        debate = await _debate_for_vote(parliament, vote_item)
    if debate is not None:
        speeches, note = await _debate_documents(deps, debate)
        documents += speeches
        if speeches:
            note = " ".join(filter(None, [_DEBATE_NOTE.format(date=debate.date), note]))
    else:
        speeches = await _law_speeches(deps, vote_item, str(payload.get("citation_title") or ""))
        documents += speeches
        days = sorted({str(d.date)[:10] for d in speeches if d.date})
        note = _LAW_DEBATE_NOTE.format(dates=", ".join(days)) if speeches else _NO_DEBATE_NOTE

    vorgang_ids = list(
        dict.fromkeys(
            [str(v) for v in payload.get("vorgang_ids") or []]
            + (vote_item.procedure_ids if vote_item else [])
        )
    )
    deps.add_scope(vorgang_ids)
    deps.settle(
        Anchor(feed_item_id=vote_item.id) if vote_item is not None else Anchor(poll_id=poll_id)
    )
    if party_ids and vorgang_ids:
        documents += await _party_documents(
            deps, vorgang_ids, party_ids, poll_id, str(payload.get("citation_title") or ""),
            {str(d.title) for d in documents if d.source_type == "parliamentary_speech"},
        )
    return DebateResult(
        documents=documents,
        note=note,
        item=vote_item.summary(deps.language) if vote_item else None,
    )


async def _party_documents(
    deps: GenericChatDeps,
    vorgang_ids: list[str],
    party_ids: list[str],
    poll_id: int,
    query: str,
    shown: set[str],
) -> list[NumberedDocument]:
    """The other votes in the procedure (the parties' amendments among them),
    then each party's statements, motions and wider record."""
    from src.generic_chat.positions import party_positions  # noqa: PLC0415 (positions imports tools)

    out: list[NumberedDocument] = []
    try:
        view = await procedure_service.aget_procedure_view(vorgang_ids[0], party_id=None, limit=60)
        others = [
            v for v in (view.votes if view else [])
            if str(v.get("external_id")) != str(poll_id) and v.get("chunk_index", 0) == 0
        ]
        out += [
            _register_vote(deps, v).model_copy(update={"tier": "this_procedure"})
            for v in others[:_OTHER_VOTES]
        ]
        out += await party_positions(deps, vorgang_ids, party_ids, query, skip=shown)
    except Exception as exc:  # noqa: BLE001 (the vote stands without them)
        logger.warning("get_vote: party positions failed: %s", exc)
    return out


async def _law_speeches(
    deps: GenericChatDeps, vote_item: Optional[FeedItemView], query: str
) -> list[NumberedDocument]:
    if vote_item is None or not vote_item.procedure_ids:
        return []
    from src.generic_chat.process import reading_speeches  # noqa: PLC0415 (process imports tools)

    try:
        return await reading_speeches(deps, vote_item.procedure_ids, query)
    except Exception as exc:  # noqa: BLE001 (the vote stands without them)
        logger.warning("get_vote: law speeches failed: %s", exc)
        return []


async def list_feed_items(
    deps: GenericChatDeps, args: ListFeedItemsInput
) -> FeedItemsResult:
    parliament = parliament_for(deps)
    if parliament is None:
        return FeedItemsResult(note="No feed exists for this parliament.")
    since, until = sorted((args.since, args.until))
    notes: list[str] = []
    if (until - since).days > _MAX_FEED_WINDOW_DAYS:
        since = until - timedelta(days=_MAX_FEED_WINDOW_DAYS)
        notes.append(f"Window shortened to {since.isoformat()}..{until.isoformat()}.")
    raws = await aget_feed_items(parliament, since, until, kind=args.kind)
    items = []
    for raw in raws:
        try:
            item = FeedItemView.model_validate(raw)
        except ValidationError:
            continue
        in_window = since.isoformat() <= item.date[:10] <= until.isoformat()
        if item.status == "published" and in_window:
            items.append(item.summary(deps.language))
    if not items:
        notes.append("No feed items in this window.")
    return FeedItemsResult(items=items[:_MAX_FEED_ITEMS], note=" ".join(notes) or None)


# ---------------------------------------------------------------------------
# web_search
# ---------------------------------------------------------------------------


async def web_search(deps: GenericChatDeps, args: WebSearchInput) -> ToolResult:
    results, note = await web.search_web(args.query, args.scope, args.recency)
    documents: list[NumberedDocument] = []
    for result in results:
        number = deps.sources.register(
            {
                "source": result.title,
                "page": 1,
                "document_publish_date": result.date,
                "url": result.url,
                "source_document": result.domain,
                "source_type": "web",
                "preferred_outlet": result.preferred,
            }
        )
        documents.append(
            NumberedDocument(
                id=number,
                source_type="web",
                title=result.title,
                date=result.date,
                outlet=result.domain,
                preferred_outlet=result.preferred,
                text=wrap(_WEB_SNIPPET, result.snippet),
            )
        )
    if not documents and note is None:
        note = "No web results."
    return ToolResult(documents=documents, note=note)


# ---------------------------------------------------------------------------
# Anchor
# ---------------------------------------------------------------------------


async def resolve_anchor(
    deps: GenericChatDeps, anchor: Anchor
) -> Optional[AnchorContext]:
    """Register the anchor's sources first; None (logged) when it is unknown."""
    if anchor.vorgang_id is not None:
        return await _resolve_procedure_anchor(deps, anchor.vorgang_id)
    if anchor.feed_item_id is not None:
        result = await get_debate(deps, anchor.feed_item_id)
    else:
        result = await get_vote(deps, cast(int, anchor.poll_id))
    if result.item is None and not result.documents:
        logger.info("anchor miss: %s", anchor.model_dump(exclude_none=True))
        return None
    deps.learn(anchor)
    deps.learn(result)
    logger.info(
        "anchor hit: %s (%d sources)",
        anchor.model_dump(exclude_none=True),
        len(result.documents),
    )
    if result.item is not None:
        label = f"{result.item.kind} \"{result.item.headline}\" ({result.item.date})"
    else:
        first = result.documents[0]
        label = f"vote \"{first.title}\" ({first.date})"
    return AnchorContext(label=label, result=result)


async def _resolve_procedure_anchor(
    deps: GenericChatDeps, vorgang_id: str
) -> Optional[AnchorContext]:
    from src.generic_chat.process import get_process  # noqa: PLC0415 (process imports tools)

    result = await get_process(deps, GetProcessInput(vorgang_id=vorgang_id))
    if result.procedure is None:
        logger.info("anchor miss: procedure %s", vorgang_id)
        return None
    deps.learn(result)
    logger.info("anchor hit: procedure %s (%d sources)", vorgang_id, len(result.documents))
    return AnchorContext(label=f"procedure \"{result.procedure.title}\"", result=result)
