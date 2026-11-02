# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Translate feed items' German content into the other locales.

Translation never touches ``facts``: sources, speakers and vote counts are the
same object in every language, so a translation cannot alter or drop one.
Each text is sent as its own numbered segment and comes back by that number,
so the item is reassembled field by field on our side. A translation is
accepted only when it keeps the German text's structure and every number in
it; otherwise the locale stays empty and the reader sees the German text, and
the next run tries again. A translation whose German source has changed since
is dropped rather than shown.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from ingestion.feed.builder import DigestBuilder, strip_refs
from ingestion.feed.models import (
    CANONICAL_LOCALE,
    FeedItem,
    Locale,
    LocalizedContent,
    LocalizedPosition,
)
from ingestion.feed.prompts import (
    TRANSLATION_PROMPT_VERSION,
    TranslationBatch,
    format_translation_prompt,
)

logger = logging.getLogger(__name__)

_BATCH = 6
# The German headline allows 12 words; English runs a little longer.
_HEADLINE_MAX_WORDS = 16
_DIGITS_RE = re.compile(r"\d+")
# What a translation that ran on past its text looks like: a translation
# tool's footer, or a run of empty lines.
_RUNAWAY_RE = re.compile(r"deepl|translated with|\n\s*\n\s*\n", re.IGNORECASE)
_QUOTE_MARKS = " \"'„“”‚‘’»«"

SegmentField = Literal[
    "headline", "teaser", "key_point", "position", "question", "quote"
]


@dataclass(frozen=True)
class Segment:
    field: SegmentField
    # The party for a position, else unused.
    party_id: str
    text: str


@dataclass
class TranslationReport:
    translated: int = 0
    failed: int = 0
    dropped_stale: int = 0


def needs_translation(item: FeedItem, locale: Locale) -> bool:
    canonical = item.content[CANONICAL_LOCALE]
    current = item.content.get(locale)
    return (
        current is None
        or current.source_hash != canonical.source_hash
        or current.prompt_version != TRANSLATION_PROMPT_VERSION
    )


def _quote(item: FeedItem) -> Optional[str]:
    quote = item.debate.opening_quote if item.debate else None
    return quote.text if quote else None


def item_segments(item: FeedItem) -> list[Segment]:
    source = item.content[CANONICAL_LOCALE]
    segments = [Segment("headline", "", source.headline)]
    if source.teaser:
        segments.append(Segment("teaser", "", source.teaser))
    segments += [Segment("key_point", "", p) for p in source.key_points]
    segments += [Segment("position", p.party_id, p.text) for p in source.positions]
    segments += [Segment("question", "", q) for q in source.suggested_questions]
    if quote := _quote(item):
        segments.append(Segment("quote", "", quote))
    return segments


def _segment_line(ref: str, segment: Segment) -> str:
    text = " ".join(segment.text.split())
    return f"[{ref}] „{text}“" if segment.field == "quote" else f"[{ref}] {text}"


def assemble(
    item: FeedItem,
    translated: list[tuple[Segment, Optional[str]]],
    *,
    generated_by: Optional[str],
    now: datetime,
) -> LocalizedContent:
    """The item's content from its translated segments, in the German order.
    A segment that came back empty is left out, which the checks then catch."""

    def texts(field: SegmentField) -> list[tuple[Segment, str]]:
        return [
            (segment, strip_refs(text, "S"))
            for segment, text in translated
            if segment.field == field and text and text.strip()
        ]

    def first(field: SegmentField) -> Optional[str]:
        found = texts(field)
        return found[0][1] if found else None

    quote = first("quote")
    return LocalizedContent(
        headline=first("headline") or "",
        teaser=first("teaser"),
        key_points=[text for _, text in texts("key_point")],
        positions=[
            LocalizedPosition(party_id=segment.party_id, text=text)
            for segment, text in texts("position")
        ],
        suggested_questions=[text for _, text in texts("question")],
        quote_translation=quote.strip(_QUOTE_MARKS) if quote else None,
        origin="translated",
        source_hash=item.content[CANONICAL_LOCALE].source_hash,
        prompt_version=TRANSLATION_PROMPT_VERSION,
        generated_by=generated_by,
        generated_at=now,
    )


def _field_pairs(
    source: LocalizedContent,
    source_quote: Optional[str],
    translated: LocalizedContent,
) -> list[tuple[str, str, str]]:
    """(field, German, English) for every text the two share. Only called once
    the structure is known to match, so list fields pair up by position."""
    pairs = [
        ("headline", source.headline, translated.headline),
        ("teaser", source.teaser or "", translated.teaser or ""),
        ("quote", source_quote or "", translated.quote_translation or ""),
    ]
    pairs += [
        (f"key_points[{n}]", de, en)
        for n, (de, en) in enumerate(zip(source.key_points, translated.key_points))
    ]
    pairs += [
        (f"positions[{de.party_id}]", de.text, en.text)
        for de, en in zip(source.positions, translated.positions)
    ]
    pairs += [
        (f"suggested_questions[{n}]", de, en)
        for n, (de, en) in enumerate(
            zip(source.suggested_questions, translated.suggested_questions)
        )
    ]
    return pairs


def translation_problems(
    source: LocalizedContent,
    source_quote: Optional[str],
    translated: LocalizedContent,
) -> list[str]:
    """What makes a translation unfit to publish; empty when it is fit."""
    problems: list[str] = []
    if not translated.headline:
        problems.append("empty headline")
    elif len(translated.headline.split()) > _HEADLINE_MAX_WORDS:
        problems.append("headline too long")
    if bool(source.teaser) != bool(translated.teaser):
        problems.append("teaser added or missing")
    if len(source.key_points) != len(translated.key_points):
        problems.append("key point count differs")
    if [p.party_id for p in source.positions] != [
        p.party_id for p in translated.positions
    ]:
        problems.append("positions differ in parties")
    if len(source.suggested_questions) != len(translated.suggested_questions):
        problems.append("question count differs")
    if bool(source_quote) != bool(translated.quote_translation):
        problems.append("quote added or missing")
    if problems:
        return problems
    for name, de, en in _field_pairs(source, source_quote, translated):
        if _RUNAWAY_RE.search(en) or len(en) > 2 * len(de) + 80:
            problems.append(f"runaway text in {name}")
        # Per field, so a number dropped from one text is not excused by the
        # same number appearing in another.
        if missing := set(_DIGITS_RE.findall(de)) - set(_DIGITS_RE.findall(en)):
            problems.append(f"numbers lost in {name}: {sorted(missing)}")
    return problems


def _translate_batch(
    builder: DigestBuilder,
    parliament_name: str,
    batch: list[FeedItem],
    locale: Locale,
    now: datetime,
    report: TranslationReport,
) -> None:
    refs: dict[str, tuple[int, Segment]] = {}
    lines: list[str] = []
    for n, item in enumerate(batch):
        for segment in item_segments(item):
            ref = f"S{len(refs) + 1}"
            refs[ref] = (n, segment)
            lines.append(_segment_line(ref, segment))
    try:
        result, model = builder.call(
            format_translation_prompt(parliament_name, "\n".join(lines)),
            TranslationBatch,
        )
        answers = {s.ref.strip(): s.text for s in result.segments}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Translation failed for %d items: %s", len(batch), exc)
        answers, model = {}, None

    for n, item in enumerate(batch):
        translated = [
            (segment, answers.get(ref))
            for ref, (owner, segment) in refs.items()
            if owner == n
        ]
        content = assemble(item, translated, generated_by=model, now=now)
        problems = translation_problems(
            item.content[CANONICAL_LOCALE], _quote(item), content
        )
        if not problems:
            item.content[locale] = content
            report.translated += 1
            continue
        logger.warning(
            "Not publishing %s translation of %s: %s", locale, item.id, problems
        )
        report.failed += 1
        if item.content.pop(locale, None) is not None:
            report.dropped_stale += 1


def translate_items(
    items: list[FeedItem],
    builder: DigestBuilder,
    locale: Locale = "en",
    *,
    now: Optional[datetime] = None,
) -> TranslationReport:
    """Translate, in place, every item whose ``locale`` is missing or stale."""
    now = now or datetime.now(timezone.utc)
    report = TranslationReport()
    pending: dict[str, list[FeedItem]] = {}
    for item in items:
        if item.status == "published" and needs_translation(item, locale):
            pending.setdefault(item.parliament_name, []).append(item)
    for parliament_name, todo in pending.items():
        for start in range(0, len(todo), _BATCH):
            _translate_batch(
                builder,
                parliament_name,
                todo[start : start + _BATCH],
                locale,
                now,
                report,
            )
    return report
