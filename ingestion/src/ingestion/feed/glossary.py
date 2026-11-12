# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Expert terms in the feed's texts, each explained once.

A reader without political background meets terms like "Aktuelle Stunde" or
"Beschlussempfehlung" in almost every debate. The web underlines them and
shows a short explanation on hover or tap.

Two steps, after an item is generated, like the translation:

1. **Find.** One call per batch of items names the terms in each item's
   German text, with the form the text uses ("Aktuellen Stunde") and the base
   form ("Aktuelle Stunde"). A form the text does not contain verbatim is
   dropped. The item stores the refs and a hash of the text they were found
   in, so a stored item gets them without a rebuild and a changed text is
   searched again.
2. **Explain.** A base form the glossary does not hold yet gets its
   explanation, written once and stored in ``glossary/{term_id}``. A second
   call checks it, as positions are checked; one that fails is written again
   at most ``MAX_DEFINITION_ATTEMPTS`` times over later runs, and is never
   shown meanwhile.

The speakers' offices ("Bundesministerin für …") go into step 1 as well, so
their terms get explained; the web matches offices against the stored forms
rather than storing refs for them, since offices are a small closed
vocabulary.
"""

from __future__ import annotations

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
from ingestion.feed.models import CANONICAL_LOCALE, FeedItem, TermRef
from ingestion.feed.store import commit_writes
from ingestion.feed.prompts import (
    GLOSSARY_PROMPT_VERSION,
    DefinitionCheckBatch,
    TermDefinitionBatch,
    TermExtractionBatch,
    format_definition_check_prompt,
    format_definition_prompt,
    format_terms_prompt,
)

logger = logging.getLogger(__name__)

GLOSSARY_COLLECTION = "glossary"
# Over this many runs a term whose explanation keeps failing the check is
# given up on; it then stays plain text.
MAX_DEFINITION_ATTEMPTS = 3
_ITEM_BATCH = 6
_TERM_BATCH = 12
_TERMS_PER_ITEM = 4

GlossaryStatus = Literal["pending", "verified", "failed"]


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term_id: str
    # The base form: "Aktuelle Stunde".
    term: str
    # German, shown on hover; None until written.
    definition: Optional[str] = None
    # Every form the texts have used, the base form included: the web matches
    # offices against them.
    forms: list[str] = Field(default_factory=list)
    # Only "verified" is shown.
    status: GlossaryStatus = "pending"
    attempts: int = 0
    # "hand" for a definition written by us.
    generated_by: Optional[str] = None
    prompt_version: Optional[str] = None
    updated_at: datetime


@dataclass
class GlossaryReport:
    items_annotated: int = 0
    items_failed: int = 0
    defined: int = 0
    rejected: int = 0


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


def item_roles(item: FeedItem) -> list[str]:
    roles = (
        s.role
        for p in (item.debate.parties if item.debate else [])
        for s in p.speakers
        if s.role
    )
    return list(dict.fromkeys(roles))


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


def _texts_block(batch: list[FeedItem]) -> str:
    blocks = []
    for n, item in enumerate(batch):
        lines = [f"[T{n + 1}]", *item_texts(item)]
        lines += [
            f"Amt einer Rednerin oder eines Redners: {r}" for r in item_roles(item)
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _found_terms(
    result: TermExtractionBatch, batch: list[FeedItem]
) -> dict[int, list[tuple[str, str]]]:
    """Batch position -> (surface, base form), each surface verbatim in its
    item's text or one of its speakers' offices."""
    found: dict[int, list[tuple[str, str]]] = {}
    for answer in result.items:
        ref = answer.ref.strip().strip("[]").upper()
        if not ref.startswith("T") or not ref[1:].isdigit():
            continue
        n = int(ref[1:]) - 1
        if not 0 <= n < len(batch):
            continue
        haystack = [*item_texts(batch[n]), *item_roles(batch[n])]
        terms: dict[str, tuple[str, str]] = {}
        for draft in answer.terms:
            surface, term = draft.surface.strip(), draft.term.strip()
            if not surface or not term or not term_id(term):
                continue
            if not any(surface in text for text in haystack):
                logger.info(
                    "Dropped term %r: not in the text of %s", surface, batch[n].id
                )
                continue
            terms.setdefault(surface, (surface, term))
        found[n] = list(terms.values())[:_TERMS_PER_ITEM]
    return found


def find_terms(
    items: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    *,
    now: datetime,
    report: GlossaryReport,
) -> list[FeedItem]:
    """Give each item whose text changed its term refs, in place, and add
    every new term to ``glossary`` as pending. Returns the items changed. An
    item whose call failed is left as it was and tried again next run."""
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
            for n, item in enumerate(batch):
                if n not in found:
                    report.items_failed += 1
                    continue
                refs = []
                for surface, term in found[n]:
                    entry = _add_form(glossary, term, surface, now)
                    refs.append(TermRef(term_id=entry.term_id, surface=surface))
                content = item.content[CANONICAL_LOCALE]
                # Refs to offices are not stored: offices are matched by form.
                texts = item_texts(item)
                content.terms = [r for r in refs if any(r.surface in t for t in texts)]
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


def needs_definition(entry: GlossaryEntry) -> bool:
    return entry.status == "pending" or (
        entry.status == "failed" and entry.attempts < MAX_DEFINITION_ATTEMPTS
    )


def define_terms(
    glossary: dict[str, GlossaryEntry],
    builder: FeedBuilder,
    parliament_name: str,
    *,
    now: datetime,
    report: GlossaryReport,
) -> list[GlossaryEntry]:
    """Write and check the explanation of every term that needs one. Returns
    the entries that changed. A call that fails leaves its terms as they
    were: "not checked" never reads as "rejected"."""
    todo = [e for e in glossary.values() if needs_definition(e)]
    changed: list[GlossaryEntry] = []
    for start in range(0, len(todo), _TERM_BATCH):
        batch = todo[start : start + _TERM_BATCH]
        refs = {f"B{i + 1}": entry for i, entry in enumerate(batch)}
        try:
            drafts = _draft_definitions(builder, parliament_name, refs)
            verdicts = _check_definitions(builder, parliament_name, refs, drafts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Glossary definitions not written: %s", exc)
            continue
        for ref, entry in refs.items():
            draft = drafts.get(ref)
            entry.attempts += 1
            entry.updated_at = now
            entry.prompt_version = GLOSSARY_PROMPT_VERSION
            if draft and verdicts.get(ref):
                entry.definition = draft[0]
                entry.generated_by = draft[1]
                entry.status = "verified"
                report.defined += 1
            else:
                entry.status = "failed"
                report.rejected += 1
                logger.info("Definition of %r rejected", entry.term)
            changed.append(entry)
    return changed


def _draft_definitions(
    builder: FeedBuilder, parliament_name: str, refs: dict[str, GlossaryEntry]
) -> dict[str, tuple[str, str]]:
    lines = "\n".join(f"[{ref}] {entry.term}" for ref, entry in refs.items())
    result, model = builder.call(
        format_definition_prompt(parliament_name, lines), TermDefinitionBatch
    )
    drafts: dict[str, tuple[str, str]] = {}
    for answer in result.definitions:
        ref = answer.ref.strip().strip("[]").upper()
        text = " ".join(answer.definition.split())
        if ref in refs and text:
            drafts[ref] = (text, model)
    return drafts


def _check_definitions(
    builder: FeedBuilder,
    parliament_name: str,
    refs: dict[str, GlossaryEntry],
    drafts: dict[str, tuple[str, str]],
) -> dict[str, bool]:
    if not drafts:
        return {}
    lines = "\n".join(
        f"[{ref}] {refs[ref].term}: {text}" for ref, (text, _) in drafts.items()
    )
    result, _ = builder.call(
        format_definition_check_prompt(parliament_name, lines), DefinitionCheckBatch
    )
    return {
        check.ref.strip().strip("[]").upper(): check.ok
        for check in result.checks
        if check.ref.strip().strip("[]").upper() in drafts
    }


# --- the pass ---------------------------------------------------------------


def annotate_terms(
    items: list[FeedItem],
    builder: FeedBuilder,
    glossary: dict[str, GlossaryEntry],
    *,
    now: Optional[datetime] = None,
) -> tuple[list[FeedItem], list[GlossaryEntry], GlossaryReport]:
    """Find the terms of every item that needs it, then explain the new
    ones. Returns the items and glossary entries to write."""
    now = now or datetime.now(timezone.utc)
    report = GlossaryReport()
    before = {k: e.model_copy() for k, e in glossary.items()}
    changed_items = find_terms(items, builder, glossary, now=now, report=report)
    parliament_name = items[0].parliament_name if items else "Bundestag"
    define_terms(glossary, builder, parliament_name, now=now, report=report)
    changed_entries = [e for k, e in glossary.items() if before.get(k) != e]
    return changed_items, changed_entries, report


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
