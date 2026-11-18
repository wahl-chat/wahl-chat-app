# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""``get_process``: one Bundestag procedure (DIP Vorgang) for the chat.

A name is resolved against the procedure profiles; when two genuinely
different procedures remain, the result offers them as choices instead of
guessing. A resolved procedure comes back as dated steps (each citable) with
its votes, speeches per reading and Drucksache chunks matched to the
question.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import defaultdict
from typing import Callable, Optional

from src.generic_chat import tools
from src.generic_chat.positions import party_positions
from src.generic_chat.schemas import (
    Anchor,
    GenericChatDeps,
    GetProcessInput,
    NumberedDocument,
    ProcessChoice,
    ProcessInfo,
    ProcessResult,
    ProcessStep,
)
from src.services import procedure_service
from src.services.chat.service import _source_snippet
from wahlchat_common.procedures import Milestone, ProcedureKind, ProcedureRecord, milestones

logger = logging.getLogger(__name__)

_SEARCH_KINDS: tuple[ProcedureKind, ...] = ("legislation", "motion", "debate")
_CANDIDATES = 8
# Names score within a few hundredths of each other; anything this close to
# the best is a real candidate (checked on the procedure chat eval).
_SCORE_BAND = 0.05
_MAX_CHOICES = 3
_MAX_VOTES = 6
_PARTY_SPEECHES_PER_DAY = 3
_MAX_SPEECHES = 12
_MAX_DOCUMENTS = 5
_SPEECH_CHARS = 1200
_DOCUMENT_CHARS = 1500
# Ended without passing; a live or passed procedure of the same name wins.
_DEAD_MARKERS = ("Erledigt", "Abgelehnt", "Zurückgezogen", "Für erledigt erklärt")

_DIGITS = re.compile(r"^\d{1,12}$")


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\wäöüß]+", " ", text.lower()).split())


def _current_wahlperiode() -> Optional[int]:
    terms = tools.federal_terms()
    return terms[-1].wahlperiode if terms else None


def _is_dead(record: ProcedureRecord) -> bool:
    return (record.beratungsstand or "").startswith(_DEAD_MARKERS)


def _is_resolution(record: ProcedureRecord) -> bool:
    return record.vorgangstyp.startswith("Entschließungsantrag") or record.titel.startswith(
        "Entschließungsantrag"
    )


def narrow(
    name: str, ranked: list[tuple[ProcedureRecord, float]], question: str = ""
) -> list[ProcedureRecord]:
    """The candidates a name still leaves open, best first (see module doc)."""
    if not ranked:
        return []
    wanted = _norm(name)
    exact = [
        r for r, _ in ranked
        if wanted in {_norm(r.titel), _norm(short_title(r)), _norm(_choice_label(r))}
    ]
    if len(exact) == 1:
        return exact
    top = ranked[0][1]
    # Titles that contain every word of the name beat scores, which sit
    # within a few hundredths of each other for most names.
    words = _name_words(wanted)
    years = _YEAR.findall(wanted)
    candidates = [r for r, _ in ranked]
    # Users name laws by topic ("Grundgesetzänderung zur Schuldenbremse"),
    # which DIP keeps in the descriptors rather than the title.
    named = _containing(words, candidates, _title) or _containing(words, candidates, _title_and_descriptors)
    # Parallel drafts (government and coalition) share a title; the rules
    # below pick the live one.
    band = exact or named or [r for r, score in ranked if score >= top - _SCORE_BAND]
    rules = [
        lambda rs: [r for r in rs if not _is_resolution(r)],
        lambda rs: [r for r in rs if r.kind == "legislation"] if "gesetz" in wanted else rs,
        lambda rs: [r for r in rs if any(_in_year(r, y) for y in years)] if years else rs,
        # A named year may point to an earlier term.
        lambda rs: rs if years else [r for r in rs if r.wahlperiode == _current_wahlperiode()],
        lambda rs: [r for r in rs if not _is_dead(r)],
        # "Welche Ausnahmen von der Schuldenbremse hat die Grundgesetzänderung
        # 2025 eingeführt?": the question names the topic the name leaves out.
        lambda rs: _best_for(question, rs),
    ]
    for rule in rules:
        kept = rule(band)
        # A rule only narrows; it never empties the list.
        if kept:
            band = kept
    return band


_FILLER = {"gesetz", "der", "die", "das", "des", "zur", "zum", "und", "von", "für", "über", "mit", "dem", "den"}


_YEAR = re.compile(r"\b((?:19|20)\d\d)\b")


def _name_words(name: str) -> list[str]:
    """The distinctive words of a name; "Wehrdienstgesetz" → "wehrdienst",
    "Grundgesetzänderung" → "grundgesetz". Years are matched by date instead."""
    words = []
    for word in name.split():
        if _YEAR.fullmatch(word):
            continue
        # "-gesetz" names the law, so it goes; "-änderung" changes one, so
        # the law's name stays: "Grundgesetzänderung" → "grundgesetz".
        if word.endswith("gesetz") and word != "gesetz":
            stem = word.removesuffix("gesetz")
        else:
            stem = word.removesuffix("änderung")
        if stem not in _FILLER and len(stem) >= 4:
            words.append(stem)
    return words


def _title(record: ProcedureRecord) -> str:
    return _norm(record.titel)


def _title_and_descriptors(record: ProcedureRecord) -> str:
    return _norm(" ".join([record.titel, *record.deskriptoren]))


def _containing(
    words: list[str], records: list[ProcedureRecord], text: Callable[[ProcedureRecord], str]
) -> list[ProcedureRecord]:
    if not words:
        return []
    # At a word start: "grundgesetz" is in "Grundgesetzes", not in "aufgrund".
    return [r for r in records if all(_at_word_start(w, text(r)) for w in words)]


def _at_word_start(word: str, text: str) -> bool:
    return re.search(rf"\b{re.escape(word)}", text) is not None


def _best_for(question: str, records: list[ProcedureRecord]) -> list[ProcedureRecord]:
    """The records sharing the most of the question's words."""
    words = {w for w in _name_words(_norm(question)) if len(w) >= 5}
    if len(records) < 2 or not words:
        return records
    hits = {r.vorgang_id: sum(_at_word_start(w, _title_and_descriptors(r)) for w in words) for r in records}
    best = max(hits.values())
    return [r for r in records if hits[r.vorgang_id] == best] if best else records


def _in_year(record: ProcedureRecord, year: str) -> bool:
    """The year is in the title ("Haushalt 2027") or the procedure ran then."""
    dates = [s.date for s in record.stages] + ([record.started_on] if record.started_on else [])
    return year in record.titel or any(str(d.year) == year for d in dates)


# DIP titles end with their short name: "Gesetz über … (Haushaltsgesetz 2027 - HG 2027)".
_SHORT_NAME = re.compile(r"\(([^()]{4,80}?)(?: - [^()]*)?\)$")


def short_title(record: ProcedureRecord) -> str:
    found = _SHORT_NAME.search(record.titel.strip())
    return found.group(1).strip() if found else record.titel


def _choice_label(record: ProcedureRecord) -> str:
    return f"{short_title(record)} (WP {record.wahlperiode})"


def _choice(record: ProcedureRecord) -> ProcessChoice:
    stage = record.latest_stage or record.vorgangstyp
    when = record.latest_stage_on.isoformat() if record.latest_stage_on else None
    return ProcessChoice(
        vorgang_id=record.vorgang_id,
        label=_choice_label(record),
        latest_stage=f"{stage} ({when})" if when else stage,
    )


_RESOLUTION_PREFIX = re.compile(r"^Entschließungsantrag (zu[mr]?|der Fraktion[^:]*zu[mr]?)\s+", re.I)


async def _law_of(record: ProcedureRecord) -> ProcedureRecord:
    """An Entschließungsantrag stands for its law when the law can be found
    by the title it names; anything else is itself."""
    if not _is_resolution(record):
        return record
    law_title = _RESOLUTION_PREFIX.sub("", " ".join(record.titel.split()))
    if law_title == record.titel:
        return record
    # Its own spelling of the law's name differs ("(X - Abk.)" vs "- X (Abk.)"):
    # match on the words before the bracket.
    words = _name_words(_norm(law_title.split("(")[0]))
    hits = await procedure_service.asearch_procedures(law_title, limit=3, kinds=("legislation",))
    for summary, _ in hits:
        title = _norm(summary.titel)
        if words and all(w in title for w in words) and summary.vorgang_id != record.vorgang_id:
            return await procedure_service.aget_procedure(summary.vorgang_id) or record
    return record


async def resolve(
    args: GetProcessInput,
) -> tuple[Optional[ProcedureRecord], list[ProcessChoice], Optional[str]]:
    """(procedure, choices, note): one procedure, or choices, or a note."""
    if args.vorgang_id:
        record = await procedure_service.aget_procedure(args.vorgang_id)
        return record, [], None if record else f"No procedure {args.vorgang_id}."
    name = args.name or ""
    if _DIGITS.match(name.strip()):
        record = await procedure_service.aget_procedure(name.strip())
        if record is not None:
            return record, [], None
    hits = await procedure_service.asearch_procedures(
        name, limit=_CANDIDATES, party_id=args.party_id, kinds=_SEARCH_KINDS
    )
    records = {
        r.vorgang_id: r for r in await procedure_service.aget_procedures(s.vorgang_id for s, _ in hits)
    }
    ranked = [(records[s.vorgang_id], score) for s, score in hits if s.vorgang_id in records]
    left = narrow(name, ranked, args.question or "")
    if not left:
        return None, [], f"No procedure found for '{name}'."
    if len(left) == 1:
        return await _law_of(left[0]), [], None
    choices: list[ProcessChoice] = []
    for record in left:
        choice = _choice(record)
        # Two buttons with one label tell the user nothing.
        if choice.label not in {c.label for c in choices}:
            choices.append(choice)
    if len(choices) == 1:
        return await _law_of(left[0]), [], None
    return None, choices[:_MAX_CHOICES], (
        "Several procedures match this name. Your whole answer is one short"
        " question asking which one the user means; do not answer yet and"
        " ignore other tool results. The app shows the choices as buttons."
    )


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _register_step(deps: GenericChatDeps, record: ProcedureRecord, stage: Milestone) -> Optional[int]:
    if not stage.url:
        return None
    document = f"{stage.document_kind or 'Dokument'} {stage.document_number or ''}".strip()
    return deps.sources.register(
        {
            "source": f"{stage.name}: {record.titel}",
            "page": stage.pdf_page or 1,
            "document_publish_date": stage.date.isoformat(),
            # DIP's anchor names the printed page, which the viewer cannot use.
            "url": stage.url.split("#", 1)[0],
            "source_document": document,
            "source_type": "procedure_step",
        }
    )


def _steps(deps: GenericChatDeps, record: ProcedureRecord) -> list[ProcessStep]:
    steps = []
    # The feed's steps: DIP's duplicate entries merged, with their summaries.
    for stage in milestones(record.stages, record.step_summaries):
        steps.append(
            ProcessStep(
                id=_register_step(deps, record, stage),
                date=stage.date.isoformat(),
                chamber=stage.chamber,
                name=stage.name,
                document=(
                    f"{stage.document_kind} {stage.document_number}"
                    if stage.document_kind and stage.document_number
                    else None
                ),
                decisions=[
                    " · ".join(filter(None, [d.tenor, d.vote_kind, d.result, d.majority]))
                    for d in stage.decisions
                ],
                summary=stage.summary,
            )
        )
    return steps


def _info(record: ProcedureRecord) -> ProcessInfo:
    return ProcessInfo(
        vorgang_id=record.vorgang_id,
        title=record.titel,
        kind=record.kind,
        vorgangstyp=record.vorgangstyp,
        wahlperiode=record.wahlperiode,
        beratungsstand=record.beratungsstand,
        initiative=record.initiative,
        abstract=tools._clip(record.abstract, 800) or None,
        dip_url=record.dip_url,
    )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


def _spread_speeches(payloads: list[dict], party_id: Optional[str]) -> list[dict]:
    """One speech per Fraktion and reading day, or the party's first few per
    day (one chunk per speech); the newest readings first when the total runs
    over."""
    by_day: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for payload in payloads:
        key = str(payload.get("speech_key") or payload.get("source_item_id") or payload.get("chunk_key"))
        if key in seen:
            continue
        seen.add(key)
        by_day[str(payload.get("publish_date") or "")[:10]].append(payload)
    picked: dict[str, list[dict]] = {}
    room = _MAX_SPEECHES
    for day in sorted(by_day, reverse=True):
        if room <= 0:
            break
        if party_id:
            chosen = by_day[day][:_PARTY_SPEECHES_PER_DAY]
        else:
            parties: set[str] = set()
            chosen = []
            for speech in by_day[day]:
                party = str(speech.get("party_id"))
                if party not in parties:
                    parties.add(party)
                    chosen.append(speech)
        picked[day] = chosen[:room]
        room -= len(picked[day])
    return [speech for day in sorted(picked) for speech in picked[day]]


async def reading_speeches(
    deps: GenericChatDeps, vorgang_ids: list[str], query: str
) -> list[NumberedDocument]:
    """The speeches of a law's readings, every Fraktion that spoke; empty
    when none are linked."""
    for vorgang_id in vorgang_ids:
        view = await procedure_service.aget_procedure_view(vorgang_id, party_id=None, limit=60)
        if view is not None and view.speeches:
            return [
                tools._register_speech(
                    deps, p, query, tools._clip(p.get("text"), _SPEECH_CHARS)
                ).model_copy(update={"tier": "this_procedure"})
                for p in _spread_speeches(view.speeches, None)
            ]
    return []


def _register_document(deps: GenericChatDeps, payload: dict) -> NumberedDocument:
    meta = tools._meta(payload)
    title = payload.get("citation_title")
    entry = {
        "source": title,
        "page": meta.get("page_start") or 1,
        "document_publish_date": payload.get("publish_date"),
        "url": payload.get("citation_url") or meta.get("pdf_url"),
        "source_document": title,
        "source_type": "drucksache",
    }
    parties = payload.get("party_ids") or []
    if len(parties) == 1:
        entry["party_id"] = parties[0]
    # The chunk opens with a breadcrumb line that is not in the PDF.
    body = str(payload.get("text") or "").split("\n\n", 1)[-1]
    snippet = _source_snippet(body)
    if snippet:
        entry["snippet"] = snippet
    number = deps.sources.register(entry)
    authors = ", ".join(meta.get("urheber") or [])
    section = " › ".join(meta.get("section_path") or [])
    return NumberedDocument(
        id=number,
        source_type="drucksache",
        title=title,
        date=payload.get("publish_date"),
        party=authors or None,
        text="\n".join(
            filter(
                None,
                [
                    f"{meta.get('doc_type') or 'Drucksache'} by {authors}" if authors else None,
                    f"Section: {section}" if section else None,
                    tools._clip(payload.get("text"), _DOCUMENT_CHARS),
                ],
            )
        ),
    )


async def _evidence(
    deps: GenericChatDeps, record: ProcedureRecord, args: GetProcessInput
) -> list[NumberedDocument]:
    view, documents = await asyncio.gather(
        procedure_service.aget_procedure_view(record.vorgang_id, party_id=args.party_id, limit=60),
        procedure_service.asearch_procedure_documents(
            args.question or record.titel, vorgang_id=record.vorgang_id, limit=_MAX_DOCUMENTS
        ),
    )
    out: list[NumberedDocument] = []
    if view is not None:
        out += [tools._register_vote(deps, p) for p in view.votes[:_MAX_VOTES]]
        query = args.question or record.titel
        out += [
            tools._register_speech(deps, p, query, tools._clip(p.get("text"), _SPEECH_CHARS))
            for p in _spread_speeches(view.speeches, args.party_id)
        ]
    out += [_register_document(deps, p) for p in documents]
    # All of it belongs to the procedure itself.
    return [doc.model_copy(update={"tier": "this_procedure"}) for doc in out]


def _anchored_choice(deps: GenericChatDeps, choices: list[ProcessChoice]) -> str:
    """The choice the anchor's documents point to, else the best ranked."""
    documents = (getattr(deps.anchor.result, "documents", None) or []) if deps.anchor else []
    linked = {ref.vorgang_id for doc in documents for ref in getattr(doc, "procedures", None) or []}
    return next((c.vorgang_id for c in choices if c.vorgang_id in linked), choices[0].vorgang_id)


async def get_process(deps: GenericChatDeps, args: GetProcessInput) -> ProcessResult:
    record, choices, note = await resolve(args)
    if record is None and choices and deps.anchor is not None:
        # An attached item already says which one is meant: never ask then.
        record = await procedure_service.aget_procedure(_anchored_choice(deps, choices))
    if record is None:
        return ProcessResult(choices=choices, note=note)
    steps = _steps(deps, record)
    documents = await _evidence(deps, record, args)
    deps.add_scope([record.vorgang_id])
    deps.settle(Anchor(vorgang_id=record.vorgang_id))
    if args.party_id:
        shown = {str(d.title) for d in documents if d.source_type == "parliamentary_speech"}
        documents += await party_positions(
            deps, [record.vorgang_id], [args.party_id], args.question or record.titel, skip=shown
        )
    notes = []
    if not steps:
        notes.append("DIP lists no dated steps for this procedure yet.")
    return ProcessResult(
        procedure=_info(record),
        steps=steps,
        documents=documents,
        note=" ".join(notes) or None,
    )
