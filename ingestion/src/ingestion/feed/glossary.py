"""Expert terms in the feed's texts, each explained once, from official pages.

A reader without political background meets terms like "Aktuelle Stunde" or
"Beschlussempfehlung" in almost every debate. The web underlines them and
shows a short explanation on hover or tap, with a link to its source.

Two steps, after an item is generated, like the translation:

1. **Find.** One call per batch of items names the terms in each item's
   German text, with the form the text uses ("Aktuellen Stunde") and the base
   form ("Aktuelle Stunde"). A form the text does not contain as whole words
   is dropped, and a second call checks that every new form is the same term
   as its base form, not a related one: the web underlines every stored form
   in offices and Gremium roles, so a wrong one would mislabel every office
   that contains it. The item stores the refs and a hash of the text they
   were found in, so a stored item gets them without a rebuild and a changed
   text is searched again.
2. **Explain.** A base form the glossary does not hold yet is looked up on
   official pages (``glossary_sources``), explained from what those pages
   say, and checked claim by claim against them, as positions are checked
   against speeches. Only an explanation that passes is shown, with its
   sources stored. One that fails is written again at most
   ``MAX_DEFINITION_ATTEMPTS`` times over later runs that publish; a call that
   fails or leaves a term out counts as no attempt. Hand-written entries are
   checked against their own sources, never rewritten. A new
   ``GLOSSARY_PROMPT_VERSION`` checks every stored entry again.

The speakers' offices ("Bundesministerin für …") go into step 1 as well, so
their terms get explained; the web matches offices against the stored forms
rather than storing refs for them, since offices are a small closed
vocabulary.

Every other locale gets the same in the same run:

3. **Translate.** An entry is translated, term and definition, in the pass
   that verifies it, and again whenever its German changes or
   ``GLOSSARY_TRANSLATION_PROMPT_VERSION`` does. A translation that loses a
   number or runs on is not stored, and the reader sees the German entry.
4. **Map.** Once an item's German terms are known and it has a translation,
   one call per batch names, for each German ref, the words that render the
   term in the translated text. Words the translated text does not contain as
   whole words are dropped, like German forms, so the web never underlines
   something that is not there.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ingestion.feed.builder import FeedBuilder
from ingestion.feed.calendar import fetch_page
from ingestion.feed.glossary_sources import (
    Fetch,
    GlossarySource,
    Research,
    ResearchFn,
    SourcePassage,
    grounded_research,
    read_sources,
)
from ingestion.feed.items import item_roles
from ingestion.feed.models import (
    CANONICAL_LOCALE,
    TRANSLATED_LOCALES,
    FeedItem,
    Locale,
    TermRef,
)
from ingestion.feed.prompts import (
    GLOSSARY_PROMPT_VERSION,
    GLOSSARY_TRANSLATION_PROMPT_VERSION,
    TERM_MAPPING_PROMPT_VERSION,
    DefinitionCheckBatch,
    FormCheckBatch,
    TermDefinitionBatch,
    TermExtractionBatch,
    TermSurfaceBatch,
    format_definition_check_prompt,
    format_definition_prompt,
    format_form_check_prompt,
    format_glossary_translation_prompt,
    format_term_mapping_prompt,
    format_terms_prompt,
)
from ingestion.feed.store import commit_writes
from ingestion.feed.translate import request_segments, segment_line, text_problems

logger = logging.getLogger(__name__)

GLOSSARY_COLLECTION = "glossary"
# Over this many runs a term whose explanation keeps failing the check is
# given up on, until the prompt version changes; it then stays plain text.
MAX_DEFINITION_ATTEMPTS = 3
HAND = "hand"
_ITEM_BATCH = 6
_TERM_BATCH = 12
_TERMS_PER_ITEM = 4
# Two segments per entry: the term and its definition.
_TRANSLATION_BATCH = 20
# A German base form has a few words; its English rendering a few more.
_TERM_MAX_WORDS = 8
_QUOTES = " \"'„“”‚‘’»«"

GlossaryStatus = Literal["pending", "verified", "failed"]


class GlossaryTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The base form in this locale: "topical hour".
    term: str
    definition: str
    # Hash of the German term and definition it was made from, so a
    # translation of an older definition is detectable without a diff.
    source_hash: str
    prompt_version: str
    generated_by: Optional[str] = None
    generated_at: datetime


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term_id: str
    # The base form: "Aktuelle Stunde".
    term: str
    # German, shown on hover; None until written.
    definition: Optional[str] = None
    # Every form the texts have used, the base form included, each checked
    # to be this term: the web matches offices against them.
    forms: list[str] = Field(default_factory=list)
    # The official pages the definition rests on; the web links the first.
    sources: list[GlossarySource] = Field(default_factory=list)
    # Only "verified" is shown.
    status: GlossaryStatus = "pending"
    # Under the current prompt version.
    attempts: int = 0
    # "hand" for a definition written by us.
    generated_by: Optional[str] = None
    # The version it was last checked under; None until it is.
    prompt_version: Optional[str] = None
    # Term and definition in every other locale; shown only while the entry
    # is verified, and only while its ``source_hash`` matches the German.
    translations: dict[Locale, GlossaryTranslation] = Field(default_factory=dict)
    updated_at: datetime


@dataclass
class GlossaryReport:
    items_annotated: int = 0
    items_failed: int = 0
    forms_rejected: int = 0
    defined: int = 0
    rejected: int = 0
    entries_translated: int = 0
    entries_translation_failed: int = 0
    # Items whose translations got their terms (step 4), or kept the old ones
    # because the call failed.
    items_mapped: int = 0
    items_map_failed: int = 0

    def add(self, other: GlossaryReport) -> None:
        for name, value in vars(other).items():
            setattr(self, name, getattr(self, name) + value)


def term_id(term: str) -> str:
    """ "Aktuelle Stunde" -> "aktuelle-stunde"; umlauts spelled out."""
    text = term.casefold().replace("ß", "ss")
    for umlaut, spelled in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(umlaut, spelled)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


# --- step 1: find -----------------------------------------------------------


def item_texts(item: FeedItem) -> list[str]:
    """The German texts the web underlines terms in. The headline stays
    plain: it is the card's link."""
    content = item.content[CANONICAL_LOCALE]
    return [
        text
        for text in (
            content.teaser,
            *content.key_points,
            *(p.text for p in content.positions),
        )
        if text
    ]


def terms_hash(item: FeedItem) -> str:
    payload = {
        "texts": item_texts(item),
        "roles": item_roles(item),
        "prompt": GLOSSARY_PROMPT_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def needs_terms(item: FeedItem) -> bool:
    return item.status == "published" and item.content[
        CANONICAL_LOCALE
    ].terms_hash != terms_hash(item)


def has_word(text: str, surface: str) -> bool:
    """``surface`` in ``text`` as whole words, as the web underlines it:
    "Stunde" is not in "Stundenlohn"."""
    return re.search(rf"(?<![^\W_]){re.escape(surface)}(?![^\W_])", text) is not None


def sentence_with(texts: list[str], surface: str) -> str:
    """The sentence ``surface`` stands in, for the checks' context."""
    for text in texts:
        if has_word(text, surface):
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                if has_word(sentence, surface):
                    return sentence[:300]
    return ""


def _texts_block(batch: list[FeedItem]) -> str:
    blocks = []
    for n, item in enumerate(batch):
        lines = [f"[T{n + 1}]", *item_texts(item)]
        lines += [
            f"Amt einer Rednerin oder eines Redners: {r}" for r in item_roles(item)
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _ref_number(ref: str, prefix: str) -> Optional[int]:
    ref = ref.strip().strip("[]").upper()
    if not ref.startswith(prefix) or not ref[len(prefix) :].isdigit():
        return None
    return int(ref[len(prefix) :]) - 1


def _found_terms(
    result: TermExtractionBatch, batch: list[FeedItem]
) -> dict[int, list[tuple[str, str]]]:
    """Batch position -> (surface, base form), each surface whole words in
    its item's text or one of its speakers' offices."""
    found: dict[int, list[tuple[str, str]]] = {}
    for answer in result.items:
        n = _ref_number(answer.ref, "T")
        if n is None or not 0 <= n < len(batch):
            continue
        haystack = [*item_texts(batch[n]), *item_roles(batch[n])]
        terms: dict[str, tuple[str, str]] = {}
        for draft in answer.terms:
            surface, term = draft.surface.strip(), draft.term.strip()
            if not surface or not term or not term_id(term):
                continue
            if not any(has_word(text, surface) for text in haystack):
                logger.info(
                    "Dropped term %r: not in the text of %s", surface, batch[n].id
                )
                continue
            terms.setdefault(surface, (surface, term))
        found[n] = list(terms.values())[:_TERMS_PER_ITEM]
    return found


def _known_form(glossary: dict[str, GlossaryEntry], term: str, surface: str) -> bool:
    """A mapping that needs no check: the base form itself, or a form
    already checked for this term."""
    if surface == term:
        return True
    entry = glossary.get(term_id(term))
    return entry is not None and surface in entry.forms


@dataclass(frozen=True)
class _Mapping:
    position: int
    surface: str
    term: str
    sentence: str


def _check_forms(
    builder: FeedBuilder, parliament_name: str, rows: list[tuple[str, str, str]]
) -> dict[int, bool]:
    """Row index -> whether its form is that term. A row the answer leaves
    out is missing, not rejected."""
    lines = []
    for i, (surface, term, sentence) in enumerate(rows):
        line = f"[F{i + 1}] „{surface}“ → „{term}“"
        if sentence:
            line += f"\n   Satz: „{sentence}“"
        lines.append(line)
    result, _ = builder.call(
        format_form_check_prompt(parliament_name, "\n".join(lines)), FormCheckBatch
    )
    verdicts: dict[int, bool] = {}
    for check in result.checks:
        row = _ref_number(check.ref, "F")
        if row is not None and 0 <= row < len(rows):
            verdicts[row] = check.ok
    return verdicts


def find_terms(
    items: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    *,
    now: datetime,
    report: GlossaryReport,
    contexts: Optional[dict[str, str]] = None,
    confirmed: Optional[set[tuple[str, str]]] = None,
) -> list[FeedItem]:
    """Give each item whose text changed its term refs, in place, and add
    every new term to ``glossary`` as pending. Returns the items changed. An
    item whose call failed, or whose new form the check left unanswered, is
    left as it was and tried again next run.

    ``contexts`` collects a sentence each new term stood in, ``confirmed``
    the (term id, form) pairs checked here.
    """
    contexts = {} if contexts is None else contexts
    confirmed = set() if confirmed is None else confirmed
    pending: dict[str, list[FeedItem]] = {}
    for item in items:
        if needs_terms(item):
            pending.setdefault(item.parliament_name, []).append(item)
    changed: list[FeedItem] = []
    for parliament_name, todo in pending.items():
        for start in range(0, len(todo), _ITEM_BATCH):
            batch = todo[start : start + _ITEM_BATCH]
            try:
                result, _ = builder.call(
                    format_terms_prompt(parliament_name, _texts_block(batch)),
                    TermExtractionBatch,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Terms not found for %d items: %s", len(batch), exc)
                report.items_failed += len(batch)
                continue
            found = _found_terms(result, batch)
            mappings = [
                _Mapping(
                    n,
                    surface,
                    term,
                    sentence_with(
                        [*item_texts(batch[n]), *item_roles(batch[n])], surface
                    ),
                )
                for n, pairs in found.items()
                for surface, term in pairs
            ]
            unchecked = [
                m for m in mappings if not _known_form(glossary, m.term, m.surface)
            ]
            verdicts: dict[_Mapping, bool] = {}
            if unchecked:
                try:
                    by_row = _check_forms(
                        builder,
                        parliament_name,
                        [(m.surface, m.term, m.sentence) for m in unchecked],
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Term forms not checked: %s", exc)
                    by_row = {}
                verdicts = {unchecked[i]: ok for i, ok in by_row.items()}
            open_items = {m.position for m in unchecked if m not in verdicts}
            for n, item in enumerate(batch):
                if n not in found or n in open_items:
                    report.items_failed += 1
                    continue
                refs = []
                for m in (m for m in mappings if m.position == n):
                    if m in verdicts and not verdicts[m]:
                        logger.info("Form %r is not the term %r", m.surface, m.term)
                        report.forms_rejected += 1
                        continue
                    entry = _add_form(glossary, m.term, m.surface, now)
                    confirmed.add((entry.term_id, m.surface))
                    if m.sentence:
                        contexts.setdefault(entry.term_id, m.sentence)
                    refs.append(TermRef(term_id=entry.term_id, surface=m.surface))
                content = item.content[CANONICAL_LOCALE]
                # Refs to offices are not stored: offices are matched by form.
                texts = item_texts(item)
                content.terms = [
                    r for r in refs if any(has_word(t, r.surface) for t in texts)
                ]
                content.terms_hash = terms_hash(item)
                changed.append(item)
                report.items_annotated += 1
    return changed


def _add_form(
    glossary: dict[str, GlossaryEntry], term: str, surface: str, now: datetime
) -> GlossaryEntry:
    key = term_id(term)
    entry = glossary.get(key)
    if entry is None:
        entry = GlossaryEntry(term_id=key, term=term, forms=[term], updated_at=now)
        glossary[key] = entry
    if surface not in entry.forms:
        entry.forms = [*entry.forms, surface]
        entry.updated_at = now
    return entry


# --- step 2: explain --------------------------------------------------------


def is_stale(entry: GlossaryEntry) -> bool:
    """Checked under an older prompt version, or never checked at all."""
    return entry.prompt_version != GLOSSARY_PROMPT_VERSION


def needs_definition(entry: GlossaryEntry) -> bool:
    if entry.generated_by == HAND:
        return entry.status == "pending" or is_stale(entry)
    if entry.status == "pending":
        return True
    if is_stale(entry):
        return True
    return entry.status == "failed" and entry.attempts < MAX_DEFINITION_ATTEMPTS


@dataclass(frozen=True)
class _Draft:
    text: str
    model: str
    sources: list[GlossarySource]


def define_terms(
    glossary: dict[str, GlossaryEntry],
    builder: FeedBuilder,
    parliament_name: str,
    *,
    now: datetime,
    report: GlossaryReport,
    research: ResearchFn = grounded_research,
    fetch: Fetch = fetch_page,
    contexts: Optional[dict[str, str]] = None,
    confirmed: Optional[set[tuple[str, str]]] = None,
) -> None:
    """Write, or check again, the explanation of every term that needs it,
    in place, and translate every verified one whose translation is missing or
    stale. A call that fails, a source that cannot be read or a term an
    answer leaves out changes nothing: "not checked" never reads as
    "rejected"."""
    contexts = contexts or {}
    todo = [e for e in glossary.values() if needs_definition(e)]
    for entry in todo:
        if is_stale(entry) and entry.status != "pending":
            entry.attempts = 0
    _recheck_forms(builder, parliament_name, todo, confirmed or set(), now, report)
    hand = [e for e in todo if e.generated_by == HAND]
    if hand:
        _check_hand_entries(hand, builder, parliament_name, fetch, now, report)
    generated = [e for e in todo if e.generated_by != HAND]
    for start in range(0, len(generated), _TERM_BATCH):
        batch = generated[start : start + _TERM_BATCH]
        refs = {f"B{i + 1}": entry for i, entry in enumerate(batch)}
        _define_batch(
            refs, builder, parliament_name, research, fetch, contexts, now, report
        )
    # In the same pass, so an entry verified here is written with its
    # translations unless they fail.
    translate_entries(glossary, builder, parliament_name, now=now, report=report)


def _recheck_forms(
    builder: FeedBuilder,
    parliament_name: str,
    entries: list[GlossaryEntry],
    confirmed: set[tuple[str, str]],
    now: datetime,
    report: GlossaryReport,
) -> None:
    """Check the forms of entries checked under an older version, or seeded,
    that this run has not checked yet; drop those that are another term."""
    rows = [
        (entry, form)
        for entry in entries
        for form in entry.forms
        if form != entry.term and (entry.term_id, form) not in confirmed
    ]
    if not rows:
        return
    try:
        verdicts = _check_forms(
            builder, parliament_name, [(form, e.term, "") for e, form in rows]
        )
    except Exception as exc:  # noqa: BLE001 — the forms stay until checked
        logger.warning("Stored term forms not checked: %s", exc)
        return
    for i, (entry, form) in enumerate(rows):
        if verdicts.get(i) is False:
            logger.warning("Form %r dropped from %r: another term", form, entry.term)
            entry.forms = [f for f in entry.forms if f != form]
            entry.updated_at = now
            report.forms_rejected += 1


async def _research_all(
    builder: FeedBuilder,
    research: ResearchFn,
    parliament_name: str,
    refs: dict[str, GlossaryEntry],
    contexts: dict[str, str],
) -> dict[str, Research | BaseException]:
    gate = asyncio.Semaphore(builder.concurrency)

    async def one(entry: GlossaryEntry) -> Research:
        async with gate:
            return await builder.bounded(
                research(parliament_name, entry.term, contexts.get(entry.term_id, ""))
            )

    found = await asyncio.gather(
        *(one(entry) for entry in refs.values()), return_exceptions=True
    )
    return dict(zip(refs, found))


def _define_batch(
    refs: dict[str, GlossaryEntry],
    builder: FeedBuilder,
    parliament_name: str,
    research: ResearchFn,
    fetch: Fetch,
    contexts: dict[str, str],
    now: datetime,
    report: GlossaryReport,
) -> None:
    found = builder.run(
        _research_all(builder, research, parliament_name, refs, contexts)
    )
    passages: dict[str, list[SourcePassage]] = {}
    for ref, entry in refs.items():
        result = found[ref]
        if isinstance(result, BaseException):
            logger.warning("No search for %r: %s", entry.term, result)
            continue
        if not result.sources:
            _reject(entry, "no official page explains it", now, report)
            continue
        read = read_sources(result.sources, entry.forms or [entry.term], fetch)
        if not read:
            logger.warning("No source for %r could be read", entry.term)
            continue
        passages[ref] = read
    if not passages:
        return
    try:
        drafts = _draft_definitions(builder, parliament_name, refs, passages, contexts)
        verdicts = _check_definitions(
            builder,
            parliament_name,
            {ref: (refs[ref].term, d.text) for ref, d in drafts.items() if d.sources},
            passages,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Glossary definitions not written: %s", exc)
        return
    for ref in passages:
        entry, draft = refs[ref], drafts.get(ref)
        if draft is None:
            continue
        if not draft.sources:
            _reject(entry, "its sources do not explain it", now, report)
        elif ref not in verdicts:
            continue
        elif verdicts[ref]:
            entry.definition = draft.text
            entry.generated_by = draft.model
            entry.sources = draft.sources
            _verify(entry, now, report)
        else:
            _reject(entry, "not borne out by its sources", now, report)


def _sources_block(ref: str, read: list[SourcePassage]) -> list[str]:
    return [
        f"[{ref}-Q{q + 1}] {p.source.title} ({p.source.url})\n{p.text}"
        for q, p in enumerate(read)
    ]


def _draft_definitions(
    builder: FeedBuilder,
    parliament_name: str,
    refs: dict[str, GlossaryEntry],
    passages: dict[str, list[SourcePassage]],
    contexts: dict[str, str],
) -> dict[str, _Draft]:
    blocks = []
    for ref, read in passages.items():
        entry = refs[ref]
        lines = [f"[{ref}] {entry.term}"]
        if contexts.get(entry.term_id):
            lines.append(f"Satz: „{contexts[entry.term_id]}“")
        blocks.append("\n".join([*lines, *_sources_block(ref, read)]))
    result, model = builder.call(
        format_definition_prompt(parliament_name, "\n\n".join(blocks)),
        TermDefinitionBatch,
    )
    drafts: dict[str, _Draft] = {}
    for answer in result.definitions:
        ref = answer.ref.strip().strip("[]").upper()
        text = " ".join(answer.definition.split())
        if ref not in passages or not text:
            continue
        cited: dict[str, GlossarySource] = {}
        for source_ref in answer.sources:
            _, _, q = source_ref.strip().strip("[]").upper().partition("-Q")
            if q.isdigit() and 0 < int(q) <= len(passages[ref]):
                source = passages[ref][int(q) - 1].source
                cited.setdefault(source.url, source)
        drafts[ref] = _Draft(text, model, list(cited.values()))
    return drafts


def _check_definitions(
    builder: FeedBuilder,
    parliament_name: str,
    definitions: dict[str, tuple[str, str]],
    passages: dict[str, list[SourcePassage]],
) -> dict[str, bool]:
    """Ref -> whether every claim of its definition stands in its sources;
    ``definitions`` maps a ref to its term and definition."""
    if not definitions:
        return {}
    blocks = [
        "\n".join([f"[{ref}] {term}: {text}", *_sources_block(ref, passages[ref])])
        for ref, (term, text) in definitions.items()
    ]
    result, _ = builder.call(
        format_definition_check_prompt(parliament_name, "\n\n".join(blocks)),
        DefinitionCheckBatch,
    )
    return {
        check.ref.strip().strip("[]").upper(): check.ok
        for check in result.checks
        if check.ref.strip().strip("[]").upper() in definitions
    }


def _check_hand_entries(
    entries: list[GlossaryEntry],
    builder: FeedBuilder,
    parliament_name: str,
    fetch: Fetch,
    now: datetime,
    report: GlossaryReport,
) -> None:
    """Check our own definitions against their sources, as the generated
    ones are. One that fails is hidden and logged, never rewritten: it is
    fixed in the seed file."""
    refs = {f"H{i + 1}": entry for i, entry in enumerate(entries)}
    passages: dict[str, list[SourcePassage]] = {}
    for ref, entry in refs.items():
        if not entry.definition or not entry.sources:
            _reject(entry, "hand-written without a source", now, report)
            continue
        read = read_sources(entry.sources, entry.forms or [entry.term], fetch)
        if read:
            passages[ref] = read
    definitions = {
        ref: (refs[ref].term, refs[ref].definition or "") for ref in passages
    }
    try:
        verdicts = _check_definitions(builder, parliament_name, definitions, passages)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Hand-written definitions not checked: %s", exc)
        return
    for ref, ok in verdicts.items():
        if ok:
            _verify(refs[ref], now, report)
        else:
            _reject(refs[ref], "not borne out by its sources", now, report)
            logger.warning(
                "Hand-written definition of %r fails its sources; fix glossary.json",
                refs[ref].term,
            )


def _verify(entry: GlossaryEntry, now: datetime, report: GlossaryReport) -> None:
    entry.status = "verified"
    entry.attempts += 1
    entry.prompt_version = GLOSSARY_PROMPT_VERSION
    entry.updated_at = now
    report.defined += 1


def _reject(
    entry: GlossaryEntry, why: str, now: datetime, report: GlossaryReport
) -> None:
    entry.status = "failed"
    entry.attempts += 1
    entry.prompt_version = GLOSSARY_PROMPT_VERSION
    entry.updated_at = now
    report.rejected += 1
    logger.info("Definition of %r rejected: %s", entry.term, why)


# --- step 3: translate ------------------------------------------------------


def entry_source_hash(entry: GlossaryEntry) -> str:
    payload = {"term": entry.term, "definition": entry.definition}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def needs_entry_translation(entry: GlossaryEntry, locale: Locale) -> bool:
    """Only a verified entry is translated: nothing else is shown."""
    if entry.status != "verified" or not entry.definition:
        return False
    current = entry.translations.get(locale)
    return (
        current is None
        or current.source_hash != entry_source_hash(entry)
        or current.prompt_version != GLOSSARY_TRANSLATION_PROMPT_VERSION
    )


def entry_translation_problems(
    entry: GlossaryEntry, term: str, definition: str
) -> list[str]:
    problems = text_problems("term", entry.term, term)
    problems += text_problems("definition", entry.definition or "", definition)
    if len(term.split()) > _TERM_MAX_WORDS:
        problems.append("term too long")
    return problems


def translate_entries(
    glossary: dict[str, GlossaryEntry],
    builder: FeedBuilder,
    parliament_name: str,
    *,
    now: datetime,
    report: GlossaryReport,
    locales: tuple[Locale, ...] = TRANSLATED_LOCALES,
) -> None:
    """Translate, in place, every verified entry whose translation is missing
    or stale. One that fails its checks keeps no translation of an older
    German text; one whose call failed keeps what it had and is tried again
    next run."""
    for locale in locales:
        todo = [e for e in glossary.values() if needs_entry_translation(e, locale)]
        for start in range(0, len(todo), _TRANSLATION_BATCH):
            batch = todo[start : start + _TRANSLATION_BATCH]
            lines = []
            for i, entry in enumerate(batch):
                lines.append(segment_line(f"S{2 * i + 1}", entry.term))
                lines.append(segment_line(f"S{2 * i + 2}", entry.definition or ""))
            answers, model = request_segments(
                builder,
                format_glossary_translation_prompt(parliament_name, "\n".join(lines)),
                f"{len(batch)} glossary entries",
            )
            if not answers:
                report.entries_translation_failed += len(batch)
                continue
            for i, entry in enumerate(batch):
                term = answers.get(f"S{2 * i + 1}", "")
                definition = " ".join(answers.get(f"S{2 * i + 2}", "").split())
                problems = entry_translation_problems(entry, term, definition)
                if not problems:
                    entry.translations = {
                        **entry.translations,
                        locale: GlossaryTranslation(
                            term=term,
                            definition=definition,
                            source_hash=entry_source_hash(entry),
                            prompt_version=GLOSSARY_TRANSLATION_PROMPT_VERSION,
                            generated_by=model,
                            generated_at=now,
                        ),
                    }
                    entry.updated_at = now
                    report.entries_translated += 1
                    continue
                logger.warning(
                    "Not storing %s translation of %r: %s", locale, entry.term, problems
                )
                report.entries_translation_failed += 1
                stored = entry.translations.get(locale)
                if stored is not None and stored.source_hash != entry_source_hash(
                    entry
                ):
                    entry.translations = {
                        k: v for k, v in entry.translations.items() if k != locale
                    }
                    entry.updated_at = now


# --- step 4: map ------------------------------------------------------------


def translated_texts(item: FeedItem, locale: Locale) -> list[str]:
    """The texts of ``locale`` the web underlines terms in, as ``item_texts``
    for German."""
    content = item.content.get(locale)
    if content is None:
        return []
    return [
        text
        for text in (
            content.teaser,
            *content.key_points,
            *(p.text for p in content.positions),
        )
        if text
    ]


def translated_terms_hash(item: FeedItem, locale: Locale) -> str:
    payload = {
        "texts": translated_texts(item, locale),
        "terms": [[r.term_id, r.surface] for r in item.content[CANONICAL_LOCALE].terms],
        "prompt": TERM_MAPPING_PROMPT_VERSION,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def needs_translated_terms(item: FeedItem, locale: Locale) -> bool:
    """A translation whose text or German terms changed since its terms were
    mapped. Waits for the German terms: mapping refs that are about to change
    would be spent."""
    content = item.content.get(locale)
    return (
        item.status == "published"
        and content is not None
        and not needs_terms(item)
        and content.terms_hash != translated_terms_hash(item, locale)
    )


def _mapping_block(
    batch: list[FeedItem], locale: Locale, glossary: dict[str, GlossaryEntry]
) -> tuple[str, dict[str, tuple[int, TermRef]]]:
    """The prompt's texts, and each term's key -> its item and German ref."""
    refs: dict[str, tuple[int, TermRef]] = {}
    blocks = []
    for n, item in enumerate(batch):
        lines = [f"[T{n + 1}]", *translated_texts(item, locale), "Begriffe:"]
        for ref in item.content[CANONICAL_LOCALE].terms:
            key = f"M{len(refs) + 1}"
            refs[key] = (n, ref)
            entry = glossary.get(ref.term_id)
            base = entry.term if entry is not None else ref.surface
            lines.append(f"[{key}] „{ref.surface}“ (Grundform: {base})")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks), refs


def map_terms(
    items: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    *,
    report: GlossaryReport,
    locales: tuple[Locale, ...] = TRANSLATED_LOCALES,
) -> list[FeedItem]:
    """Give each translation whose terms are missing or stale the words that
    render its German terms, in place. Returns the items changed. An item
    whose call failed, or whose answer left a term out, keeps what it had and
    is tried again next run."""
    changed: dict[str, FeedItem] = {}
    for locale in locales:
        pending: dict[str, list[FeedItem]] = {}
        for item in items:
            if not needs_translated_terms(item, locale):
                continue
            if not item.content[CANONICAL_LOCALE].terms:
                _set_translated_terms(item, locale, [])
                changed[item.id] = item
                report.items_mapped += 1
                continue
            pending.setdefault(item.parliament_name, []).append(item)
        for parliament_name, todo in pending.items():
            for start in range(0, len(todo), _ITEM_BATCH):
                batch = todo[start : start + _ITEM_BATCH]
                for item in _map_batch(
                    batch, builder, glossary, parliament_name, locale, report
                ):
                    changed[item.id] = item
    return list(changed.values())


def _map_batch(
    batch: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    parliament_name: str,
    locale: Locale,
    report: GlossaryReport,
) -> list[FeedItem]:
    block, refs = _mapping_block(batch, locale, glossary)
    try:
        result, _ = builder.call(
            format_term_mapping_prompt(parliament_name, block), TermSurfaceBatch
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Terms not mapped for %d items: %s", len(batch), exc)
        report.items_map_failed += len(batch)
        return []
    answers: dict[str, str] = {}
    for answer in result.surfaces:
        key = answer.ref.strip().strip("[]").upper()
        if key in refs:
            answers[key] = answer.surface.strip().strip(_QUOTES).strip()
    changed: list[FeedItem] = []
    for n, item in enumerate(batch):
        keys = [k for k, (owner, _) in refs.items() if owner == n]
        if any(k not in answers for k in keys):
            report.items_map_failed += 1
            continue
        texts = translated_texts(item, locale)
        found: dict[tuple[str, str], TermRef] = {}
        for key in keys:
            surface, german = answers[key], refs[key][1]
            if not surface or not any(has_word(t, surface) for t in texts):
                logger.info(
                    "No %s words for %r in %s: %r",
                    locale,
                    german.surface,
                    item.id,
                    surface,
                )
                continue
            found.setdefault(
                (german.term_id, surface),
                TermRef(term_id=german.term_id, surface=surface),
            )
        _set_translated_terms(item, locale, list(found.values()))
        changed.append(item)
        report.items_mapped += 1
    return changed


def _set_translated_terms(item: FeedItem, locale: Locale, terms: list[TermRef]) -> None:
    content = item.content[locale]
    content.terms = terms
    content.terms_hash = translated_terms_hash(item, locale)


# --- the pass ---------------------------------------------------------------


def annotate_terms(
    items: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    *,
    now: Optional[datetime] = None,
    research: ResearchFn = grounded_research,
    fetch: Fetch = fetch_page,
) -> tuple[list[FeedItem], list[GlossaryEntry], GlossaryReport]:
    """Find the terms of every item that needs it, explain and translate the
    new ones, then find them in the items' translations. Returns the items
    and glossary entries to write."""
    now = now or datetime.now(timezone.utc)
    report = GlossaryReport()
    before = {k: e.model_copy(deep=True) for k, e in glossary.items()}
    contexts: dict[str, str] = {}
    confirmed: set[tuple[str, str]] = set()
    changed_items = find_terms(
        items,
        builder,
        glossary,
        now=now,
        report=report,
        contexts=contexts,
        confirmed=confirmed,
    )
    parliament_name = items[0].parliament_name if items else "Bundestag"
    define_terms(
        glossary,
        builder,
        parliament_name,
        now=now,
        report=report,
        research=research,
        fetch=fetch,
        contexts=contexts,
        confirmed=confirmed,
    )
    mapped = map_terms(items, builder, glossary, report=report)
    changed = {i.id: i for i in [*changed_items, *mapped]}
    changed_entries = [e for k, e in glossary.items() if before.get(k) != e]
    return list(changed.values()), changed_entries, report


# --- store ------------------------------------------------------------------


def read_glossary(db: Any) -> dict[str, GlossaryEntry]:
    """The whole glossary: a few hundred short entries at most."""
    if db is None:
        return {}
    entries: dict[str, GlossaryEntry] = {}
    for snapshot in db.collection(GLOSSARY_COLLECTION).stream():
        try:
            entry = GlossaryEntry.model_validate(snapshot.to_dict())
        except Exception as exc:  # noqa: BLE001 — one bad doc must not stop the run
            logger.warning("Glossary entry %s unreadable: %s", snapshot.id, exc)
            continue
        entries[entry.term_id] = entry
    return entries


def write_glossary(db: Any, entries: list[GlossaryEntry]) -> None:
    commit_writes(
        db,
        [
            (
                db.collection(GLOSSARY_COLLECTION).document(e.term_id),
                e.model_dump(mode="json"),
            )
            for e in entries
        ],
    )
