# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Turn one parliament's window of corpus payloads into ``DailyDigest`` docs.

LLM failure policy: a failed step never aborts the run. Votes fall back to
their source title under the ``other`` topic, a failed session summary leaves
``session`` empty, and either case stores ``input_hash=None`` so the next run
retries that day instead of skipping it as unchanged.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel

from src.daily_digest.models import (
    DailyDigest,
    DigestCitation,
    DigestProtocol,
    DigestSession,
    DigestSessionSection,
    DigestVote,
    DigestVoteParty,
    digest_doc_id,
)
from src.daily_digest.parliaments import Parliament, PartyDisplay, party_display_for
from src.daily_digest.prompts import (
    PROMPT_VERSION,
    SessionSummaryDraft,
    VoteEnrichment,
    VoteEnrichmentBatch,
    format_session_prompt,
    format_vote_prompt,
)
from src.daily_digest.reader import AgendaItem, SittingDay, parse_day
from src.daily_digest.topics import DigestTopic

logger = logging.getLogger(__name__)

_VOTE_BATCH = 12
_VOTE_CONTEXT_CHARS = 1200
_SPEECH_EXCERPT_CHARS = 900
_SPEECHES_PER_AGENDA_ITEM = 8
_SESSION_PROMPT_CHARS = 90_000
_CITATIONS_PER_SECTION = 3
_NO_AGENDA_LABEL = "Sonstige Wortbeiträge"
_DESCRIPTION_CHARS = 1500
# Part of every input_hash next to PROMPT_VERSION: bump it when the stored doc
# gains or changes a field, so existing days are rebuilt in the new shape.
DIGEST_FORMAT_VERSION = "2"
# The vote connector writes the embed text as "<label>\n\nThemen: …\n\nKontext: <intro>".
_CONTEXT_MARKER = "Kontext: "

# (messages, schema, long_form) -> parsed schema instance. long_form selects
# the answer-generation roster over the cheaper pre/post-processing one.
StructuredOutputFn = Callable[
    [list[BaseMessage], type[BaseModel], bool], Coroutine[Any, Any, Any]
]


async def _default_structured_output(
    messages: list[BaseMessage], schema: type[BaseModel], long_form: bool
) -> Any:
    from src.llms import (  # noqa: PLC0415
        PRE_AND_POST_PROCESSING_LLMS,
        RESPONSE_GENERATION_LLMS,
        get_structured_output_from_llms,
    )

    roster = RESPONSE_GENERATION_LLMS if long_form else PRE_AND_POST_PROCESSING_LLMS
    return await get_structured_output_from_llms(roster, messages, schema)


@dataclass
class VoteText:
    title: str
    short_title: str
    summary: Optional[str]
    topics: list[DigestTopic]


class DigestBuilder:
    """Runs the LLM steps on one process-wide event loop.

    The shared LLM clients cache connections bound to the loop they first ran
    on, so a per-call ``asyncio.run()`` would close that loop and break the
    next call on the same client.
    """

    def __init__(self, structured_output_fn: Optional[StructuredOutputFn] = None):
        self._fn = structured_output_fn or _default_structured_output
        self._runner = asyncio.Runner()

    def close(self) -> None:
        self._runner.close()

    def _call(self, prompt: str, schema: type[BaseModel], long_form: bool) -> Any:
        return self._runner.run(
            self._fn([HumanMessage(content=prompt)], schema, long_form)
        )

    def enrich_votes(
        self, parliament: Parliament, payloads: list[dict]
    ) -> tuple[dict[int, VoteText], set[int]]:
        """Topic tags + plain-language text per poll id, and the ids that fell back."""
        texts: dict[int, VoteText] = {}
        fallen_back: set[int] = set()
        for start in range(0, len(payloads), _VOTE_BATCH):
            batch = payloads[start : start + _VOTE_BATCH]
            refs = {f"V{i + 1}": p for i, p in enumerate(batch)}
            enriched = self._enrich_vote_batch(parliament, refs)
            for ref, payload in refs.items():
                poll_id = int(payload["external_id"])
                title = str(payload.get("citation_title") or "Abstimmung")
                item = enriched.get(ref)
                if item is None:
                    fallen_back.add(poll_id)
                    texts[poll_id] = VoteText(title, title, None, ["other"])
                    continue
                texts[poll_id] = VoteText(
                    title=title,
                    short_title=item.short_title.strip() or title,
                    summary=item.summary.strip() or None,
                    topics=list(dict.fromkeys(item.topics))[:2] or ["other"],
                )
        return texts, fallen_back

    def _enrich_vote_batch(
        self, parliament: Parliament, refs: dict[str, dict]
    ) -> dict[str, VoteEnrichment]:
        block = "\n\n".join(
            f"[{ref}] {str(p.get('text') or '')[:_VOTE_CONTEXT_CHARS]}"
            for ref, p in refs.items()
        )
        try:
            result = self._call(
                format_vote_prompt(parliament.name, block), VoteEnrichmentBatch, False
            )
            return {v.ref: v for v in result.votes if v.ref in refs}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Vote enrichment failed for %s: %s", parliament.id, exc)
            return {}

    def summarize_day(
        self, parliament: Parliament, sitting: SittingDay
    ) -> Optional[DigestSession]:
        refs = {f"A{i + 1}": item for i, item in enumerate(sitting.agenda_items)}
        prompt = format_session_prompt(
            parliament.name,
            sitting.day.strftime("%d.%m.%Y"),
            _agenda_block(refs),
        )
        try:
            draft = self._call(prompt, SessionSummaryDraft, True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Session summary failed for %s %s: %s", parliament.id, sitting.day, exc
            )
            return None
        return session_from_draft(draft, refs, sitting)


def _agenda_block(refs: dict[str, AgendaItem]) -> str:
    parts: list[str] = []
    budget = _SESSION_PROMPT_CHARS
    for ref, item in refs.items():
        lines = [f"[{ref}] {item.label}"]
        for speech in item.speeches[:_SPEECHES_PER_AGENDA_ITEM]:
            speaker = speech.speaker or "Unbekannt"
            excerpt = speech.text[:_SPEECH_EXCERPT_CHARS]
            lines.append(f"- {speaker} ({speech.party_id}): {excerpt}")
        block = "\n".join(lines)
        if len(block) > budget:
            block = block[:budget]
        parts.append(block)
        budget -= len(block)
        if budget <= 0:
            break
    return "\n\n".join(parts)


def _citations(items: list[AgendaItem]) -> list[DigestCitation]:
    citations: list[DigestCitation] = []
    seen: set[str] = set()
    for item in items:
        for speech in item.speeches:
            if not speech.citation_url or speech.citation_url in seen:
                continue
            seen.add(speech.citation_url)
            citations.append(
                DigestCitation(
                    title=speech.citation_title or speech.speaker or item.label,
                    url=speech.citation_url,
                )
            )
            if len(citations) == _CITATIONS_PER_SECTION:
                return citations
    return citations


# The model sometimes echoes the agenda ids it was given ("Kindergeld (A3)",
# "[A3, A5]") into free text; they mean nothing to a reader.
_AGENDA_REF_RE = re.compile(r"\s*[\[(]?\bA\d+(?:\s*[,;/]\s*A\d+)*\b[\])]?")


def _strip_agenda_refs(text: str) -> str:
    return _AGENDA_REF_RE.sub("", text).strip(" ,;:-")


def session_from_draft(
    draft: SessionSummaryDraft, refs: dict[str, AgendaItem], sitting: SittingDay
) -> DigestSession:
    """Ground the model's sections in real agenda items; drop any it invented."""
    sections: list[DigestSessionSection] = []
    used: set[str] = set()
    for drafted in draft.sections:
        items = [refs[r] for r in dict.fromkeys(drafted.agenda_refs) if r in refs]
        if not items:
            continue
        used.update(r for r in drafted.agenda_refs if r in refs)
        sections.append(
            DigestSessionSection(
                topic=drafted.topic,
                headline=_strip_agenda_refs(drafted.headline),
                summary=_strip_agenda_refs(drafted.summary),
                agenda_items=[item.label for item in items],
                citations=_citations(items),
                video_url=next((i.video_url for i in items if i.video_url), None),
            )
        )

    other_topics = [
        cleaned for t in draft.other_topics if (cleaned := _strip_agenda_refs(t))
    ]
    if not other_topics:
        other_topics = [
            item.label
            for ref, item in refs.items()
            if ref not in used and item.label != _NO_AGENDA_LABEL
        ]
    return DigestSession(
        protocols=[
            DigestProtocol(protocol_id=p, pdf_url=u) for p, u in sitting.protocols
        ],
        sections=sections,
        other_topics=other_topics,
    )


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


def vote_from_payload(
    payload: dict, text: VoteText, display: dict[str, PartyDisplay]
) -> DigestVote:
    results = (payload.get("meta") or {}).get("vote_results") or []
    parties = []
    for result in results:
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
    return DigestVote(
        poll_id=int(payload["external_id"]),
        title=text.title,
        short_title=text.short_title,
        summary=text.summary,
        description=vote_description(str(payload.get("text") or "")),
        topics=text.topics,
        outcome=(payload.get("meta") or {}).get("motion_outcome"),
        citation_url=payload.get("citation_url"),
        parties=parties,
    )


def compute_input_hash(vote_payloads: list[dict], sitting: Optional[SittingDay]) -> str:
    hashes = sorted(str(p.get("content_hash") or "") for p in vote_payloads)
    speech_hashes = sitting.content_hashes if sitting else []
    return hashlib.sha256(
        json.dumps(
            {
                "prompt": PROMPT_VERSION,
                "format": DIGEST_FORMAT_VERSION,
                "votes": hashes,
                "speeches": speech_hashes,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


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


def build_digests(
    parliament: Parliament,
    vote_payloads: list[dict],
    sitting_days: dict[date, SittingDay],
    display: dict[str, PartyDisplay],
    builder: DigestBuilder,
    *,
    existing_hashes: Optional[dict[str, Optional[str]]] = None,
    force: bool = False,
    now: Optional[datetime] = None,
) -> tuple[list[DailyDigest], int]:
    """Digests for every day with votes or a sitting, and how many were unchanged."""
    existing_hashes = existing_hashes or {}
    generated_at = now or datetime.now(timezone.utc)
    by_day = votes_by_day(vote_payloads)
    digests: list[DailyDigest] = []
    unchanged = 0

    for day in sorted(set(by_day) | set(sitting_days), reverse=True):
        day_votes = by_day.get(day, [])
        sitting = sitting_days.get(day)
        doc_id = digest_doc_id(parliament.id, day)
        input_hash = compute_input_hash(day_votes, sitting)
        if not force and existing_hashes.get(doc_id) == input_hash:
            unchanged += 1
            continue

        texts, fallen_back = builder.enrich_votes(parliament, day_votes)
        session = builder.summarize_day(parliament, sitting) if sitting else None
        complete = not fallen_back and (sitting is None or session is not None)

        digests.append(
            DailyDigest(
                id=doc_id,
                parliament=parliament.id,
                parliament_name=parliament.name,
                region=parliament.region,
                date=day,
                votes=[
                    vote_from_payload(p, texts[int(p["external_id"])], display)
                    for p in day_votes
                ],
                session=session,
                input_hash=input_hash if complete else None,
                generated_at=generated_at,
            )
        )
    return digests, unchanged
