# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Drucksache text → structure-aware chunks.

A Drucksache is split at its own headings first: the Vorblatt sections
(A. Problem und Ziel … F.), each Artikel of the law text, the parts of the
Begründung (A./B., I./II., Zu Artikel n) and of a committee Bericht. Inside a
section the corpus-wide splitter (1000/150) applies. Every chunk starts with
a breadcrumb naming the document and section, because "§ 2 wird wie folgt
geändert" means nothing on its own. Vorblatt and Anträge are the overview,
a committee's Bericht is the report, law text and Begründung the body
(``doc_section``). The ``overview`` mode reads overview and report only: the
S0–S3 comparison (ADR-0013) found that law text adds detail but crowds out
speeches and votes, while the Bericht adds the course and the Fraktionen's
stances.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Optional

from qdrant_client import models

from ingestion.chunking import chunk_text
from ingestion.ids import compute_source_item_id, make_chunk_key
from ingestion.procedures.mapper import NO_PARTY, party_ids_of
from ingestion.procedures.store import replace_parents
from ingestion.schemas import (
    AuthorityTier,
    ChunkRecord,
    DrucksacheMeta,
    ProcedureLink,
    SourceType,
)
from wahlchat_common.procedures import READ_BY_DEFAULT, DocSection, ProcedureRecord

logger = logging.getLogger(__name__)

DrucksacheMode = Literal["off", "overview", "full"]

# Document types worth reading; Kleine Anfragen, Antworten and Unterrichtungen
# are no procedure's argument.
TEXT_TYPES: frozenset[str] = frozenset(
    {
        "Gesetzentwurf",
        "Antrag",
        "Entschließungsantrag",
        "Änderungsantrag",
        "Beschlussempfehlung und Bericht",
        "Beschlussempfehlung",
    }
)
# Short documents whose whole text states what is asked for.
_WHOLE_OVERVIEW: frozenset[str] = frozenset({"Antrag", "Entschließungsantrag", "Änderungsantrag"})
MAX_TEXT_CHARS = 1_500_000

_VORBLATT = re.compile(r"^[A-F]\. [A-ZÄÖÜ][\wäöüß ,/-]{2,60}$")
_TOP = re.compile(
    r"^(Begründung|Beschlussempfehlung|Anlage(?: \d+)?|Bericht der Abgeordneten.*|"
    r"Stellungnahme des Nationalen Normenkontrollrates.*|"
    r"Stellungnahme des Bundesrates|Gegenäußerung der Bundesregierung)$"
)
_ARTIKEL = re.compile(r"^Artikel \d+[a-z]?$")
# Where the law text starts after the Vorblatt of a bill without Artikel
# (one law in § sections) or before its first Artikel.
_LAW_TITLE = re.compile(r"^Entwurf eines .{5,}")
_FIRST_PARAGRAPH = re.compile(r"^§ 1( .*)?$")
_PART = re.compile(r"^[AB]\. (Allgemeiner|Besonderer) Teil$")
_ROMAN = re.compile(r"^[IVX]{1,5}\. [A-ZÄÖÜ][^.]{2,120}$")
_ZU_ARTIKEL = re.compile(r"^Zu Artikel \d+[a-z]?(?: \(.{1,80}\))?$")


@dataclass(frozen=True)
class Section:
    path: tuple[str, ...]
    text: str
    doc_section: DocSection


def _heading_level(line: str, in_vorblatt: bool) -> Optional[int]:
    """1 document part, 2 Vorblatt section / Artikel / A.-B. Teil, 3 Roman
    numbered section, 4 Zu Artikel; None for body text."""
    if _TOP.match(line):
        return 1
    if (in_vorblatt and _VORBLATT.match(line)) or _ARTIKEL.match(line) or _PART.match(line):
        return 2
    if not in_vorblatt and _ROMAN.match(line):
        return 3
    if _ZU_ARTIKEL.match(line):
        return 4
    return None


def _heading_name(line: str) -> str:
    # The Bericht heading lists the rapporteurs and wraps mid-name.
    return "Bericht" if line.startswith("Bericht der Abgeordneten") else line


def _join(lines: list[str]) -> str:
    """Re-flow wrapped lines; a line starting lower-case continues the last."""
    out: list[str] = []
    for line in lines:
        if out and line and (line[0].islower() or out[-1].endswith(("-", ","))):
            joined = out[-1][:-1] + line if out[-1].endswith("-") and line[0].islower() else f"{out[-1]} {line}"
            out[-1] = joined
        elif line:
            out.append(line)
    return "\n".join(out)


def split_sections(text: str, doc_type: Optional[str]) -> list[Section]:
    """The document's sections in order, with the heading path of each."""
    lines = [line.strip() for line in text.replace("\r", "").splitlines()]
    sections: list[Section] = []
    stack: list[tuple[int, str]] = [(1, "Vorblatt")]
    body: list[str] = []
    in_vorblatt = True
    whole_overview = doc_type in _WHOLE_OVERVIEW

    def close() -> None:
        content = _join(body)
        if content.strip():
            path = tuple(name for _, name in stack)
            section: DocSection = "body"
            if whole_overview or path[0] == "Vorblatt":
                section = "overview"
            elif path[0] == "Bericht":
                section = "report"
            sections.append(Section(path, content, section))
        body.clear()

    for line in lines:
        level = _heading_level(line, in_vorblatt)
        seen_vorblatt_section = len(stack) > 1 and stack[0][1] == "Vorblatt"
        if (
            level is None
            and in_vorblatt
            and seen_vorblatt_section
            and (_LAW_TITLE.match(line) or _FIRST_PARAGRAPH.match(line))
        ):
            close()
            in_vorblatt = False
            stack = [(1, "Gesetzestext")]
            body.append(line)
            continue
        if level is None:
            body.append(line)
            continue
        close()
        if in_vorblatt and (level == 1 or _ARTIKEL.match(line)):
            in_vorblatt = False
            stack = [(1, "Gesetzestext")] if _ARTIKEL.match(line) else []
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack and level > 1:
            stack = [(1, "Gesetzestext" if _ARTIKEL.match(line) else "Text")]
        stack.append((level, _heading_name(line)))
    close()
    return sections


def _breadcrumb(number: str, doc_type: str, title: str, path: tuple[str, ...]) -> str:
    return f"Drucksache {number} · {doc_type}: {title} · {' › '.join(path)}"


def _plain_title(raw: str) -> str:
    """DIP titles of committee reports start with 'zu dem Gesetzentwurf …';
    the procedure's own name is their last line."""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return " ".join((lines[-1] if lines else "").split())


def drucksache_chunks(
    doc: dict[str, Any],
    *,
    procedures: dict[str, ProcedureRecord],
    mode: DrucksacheMode,
    today: date,
) -> list[ChunkRecord]:
    """Chunks of one DIP ``drucksache-text`` document; [] when mode is off."""
    if mode == "off":
        return []
    number = str(doc["dokumentnummer"])
    doc_type = str(doc.get("drucksachetyp") or "Drucksache")
    text = str(doc.get("text") or "")
    if len(text) > MAX_TEXT_CHARS:
        logger.warning("Drucksache %s: %d chars, skipped", number, len(text))
        return []
    vorgang_ids = sorted(
        {str(ref["id"]) for ref in doc.get("vorgangsbezug") or []} & set(procedures)
    )
    titles = [procedures[v].titel for v in vorgang_ids]
    title = titles[0] if titles else _plain_title(str(doc.get("titel") or ""))
    sachgebiete = sorted({s for v in vorgang_ids for s in procedures[v].sachgebiete})
    urheber = [str(u.get("titel") or u) if isinstance(u, dict) else str(u) for u in doc.get("urheber") or []]
    parties = party_ids_of(urheber)
    fundstelle = doc.get("fundstelle") or {}
    pdf_url = fundstelle.get("pdf_url")
    publish_date = _day(doc.get("datum")) or today
    wahlperiode = int(number.split("/")[0]) if "/" in number else None
    source_item_id = compute_source_item_id(SourceType.DRUCKSACHE.value, f"BT:{number}")

    chunks: list[ChunkRecord] = []
    for section in split_sections(text, doc_type):
        if mode == "overview" and section.doc_section not in READ_BY_DEFAULT:
            continue
        crumb = _breadcrumb(number, doc_type, title, section.path)
        for piece in chunk_text(section.text):
            index = len(chunks)
            body = f"{crumb}\n\n{piece}"
            meta = DrucksacheMeta(
                number=number,
                doc_type=doc_type,
                title=title,
                urheber=urheber,
                section_path=list(section.path),
                pdf_url=pdf_url,
            ).model_dump(mode="json", exclude_none=True)
            content_hash = hashlib.sha256(
                json.dumps(
                    {
                        "text": body,
                        "meta": meta,
                        "parties": parties,
                        "vorgang_ids": vorgang_ids,
                        "sachgebiete": sachgebiete,
                        "doc_section": section.doc_section,
                        "publish_date": publish_date.isoformat(),
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()
            chunks.append(
                ChunkRecord(
                    chunk_key=make_chunk_key(source_item_id, index),
                    source_item_id=source_item_id,
                    chunk_index=index,
                    text=body,
                    party_id=parties[0] if len(parties) == 1 else NO_PARTY,
                    party_ids=parties or None,
                    region="DE",
                    # A Fraktion's own paper states its position; the rest
                    # (government bills, committee reports) is the record.
                    authority_tier=(
                        AuthorityTier.SELF_REPORTED if parties else AuthorityTier.FACTUAL_RECORD
                    ),
                    source_type=SourceType.DRUCKSACHE,
                    publish_date=publish_date,
                    citation_url=pdf_url,
                    citation_title=f"Drucksache {number}: {title}",
                    wahlperiode=wahlperiode,
                    source_parent_key=f"{SourceType.DRUCKSACHE.value}:BT:{number}",
                    content_hash=content_hash,
                    vorgang_ids=vorgang_ids or None,
                    sachgebiete=sachgebiete or None,
                    procedure_link=ProcedureLink(method="source", checked_on=today),
                    doc_section=section.doc_section,
                    meta=meta,
                )
            )
    return chunks


def _day(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def wanted_numbers(procedures: dict[str, ProcedureRecord]) -> set[str]:
    """BT Drucksachen of a readable type among the stored procedures'."""
    return {
        ref.number
        for record in procedures.values()
        for ref in record.drucksachen
        if ref.chamber == "BT" and ref.doc_type in TEXT_TYPES
    }


@dataclass
class DrucksacheReport:
    documents: int = 0
    chunks: int = 0
    written: int = 0
    skipped: int = 0
    failed: list[str] = field(default_factory=list)
    # Read, but nothing to chunk (too long, or no text in a readable section).
    empty: list[str] = field(default_factory=list)


def stored_drucksachen(qdrant: Any, collection: str) -> set[str]:
    """Numbers of the Drucksachen with chunks in the collection."""
    result = qdrant.facet(
        collection_name=collection,
        key="source_parent_key",
        facet_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="source_type", match=models.MatchValue(value=SourceType.DRUCKSACHE.value)
                )
            ]
        ),
        limit=1_000_000,
        exact=True,
    )
    prefix = f"{SourceType.DRUCKSACHE.value}:BT:"
    return {str(hit.value)[len(prefix) :] for hit in result.hits if str(hit.value).startswith(prefix)}


def ingest_drucksachen(
    numbers: Iterable[str],
    *,
    dip: Any,
    qdrant: Any,
    collection: str,
    embed: Any,
    procedures: dict[str, ProcedureRecord],
    mode: DrucksacheMode,
    today: date,
    batch_size: int = 10,
) -> DrucksacheReport:
    """Read, chunk and write the given Drucksachen, a batch at a time.

    A document DIP has no text for yet keeps whatever is stored; a failing
    batch is reported and retried next run.
    """
    report = DrucksacheReport()
    ordered = sorted(set(numbers))
    for start in range(0, len(ordered), batch_size):
        batch = ordered[start : start + batch_size]
        try:
            texts = dip.drucksache_texts(batch)
        except Exception:  # noqa: BLE001 — retried next run
            logger.exception("Drucksache texts failed for %s", batch)
            report.failed.extend(batch)
            continue
        parents = {
            f"{SourceType.DRUCKSACHE.value}:BT:{number}": drucksache_chunks(
                doc, procedures=procedures, mode=mode, today=today
            )
            for number, doc in texts.items()
        }
        report.documents += len(parents)
        report.empty.extend(k.rsplit(":", 1)[-1] for k, chunks in parents.items() if not chunks)
        report.chunks += sum(len(c) for c in parents.values())
        written = replace_parents(qdrant, collection, embed, parents)
        report.written += written.written
        report.skipped += written.skipped
        report.failed.extend(k.rsplit(":", 1)[-1] for k in written.failed_parents)
        logger.info(
            "Drucksachen %d/%d: %d chunks so far", min(start + batch_size, len(ordered)), len(ordered), report.chunks
        )
    return report
