# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Short summaries of a law's draft and committee report for the feed timeline.

The timeline's other steps say enough as facts (who, when, the tally); the
draft and the committee's recommendation are where the content is. Each is
summarised once from its Drucksache's overview (Vorblatt) and kept until that
text changes. A second call checks the summary against the text, as the feed
does with party positions: a summary it does not confirm is written once
more with the objections, and if that fails too, the step shows facts only.

Only laws a feed item points to are summarised: they are the ones a reader
can open.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable, Optional

from langchain_core.messages import BaseMessage, HumanMessage
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient, models

from ingestion.schemas import SourceType
from wahlchat_common.procedures import ProcedureRecord, ProcedureStage, StepSummary

logger = logging.getLogger(__name__)

SUMMARISED_STAGES = ("Gesetzentwurf", "Beschlussempfehlung")
_MAX_TEXT_CHARS = 14_000
_CONCURRENCY = 4

WRITE_PROMPT = """\
Du schreibst für eine neutrale Übersicht des Bundestags, die Bürgerinnen und \
Bürger ohne Fachwissen lesen. Fasse die folgende Drucksache in ein bis zwei \
Sätzen zusammen (höchstens 45 Wörter): Was soll sich ändern?

Regeln:
- Nur, was im Text steht. Keine Folgen, Bewertungen oder Hintergründe ergänzen.
- Schreibe zu, wer etwas will oder empfiehlt: „Die Bundesregierung will …“, \
„Der Innenausschuss empfiehlt …“. Ziele und Begründungen sind die Sicht der \
Urheber, keine Tatsachen.
- Bei einer Beschlussempfehlung: nur, was der Ausschuss am Entwurf ändern \
will, nicht den ganzen Entwurf noch einmal.
- Einfache Sprache, keine Paragrafen, keine Drucksachennummern, keine \
Abkürzungen ohne Erklärung.

Drucksache: {doc_type} „{title}“
Urheber: {urheber}
{feedback}
Text (Vorblatt):
{text}
"""

CHECK_PROMPT = """\
Du prüfst eine Zusammenfassung, bevor sie in einer neutralen Übersicht des \
Bundestags erscheint. Prüfe jede Aussage gegen den Text der Drucksache.

Sie ist nur dann belegt, wenn
- jede Aussage im Text steht (nichts hinzugefügt, nichts zugespitzt),
- Ziele und Begründungen den Urhebern zugeschrieben sind, nicht als Tatsache,
- bei einer Beschlussempfehlung nur die Änderungen des Ausschusses genannt sind.

Zusammenfassung:
{summary}

Drucksache: {doc_type} „{title}“, Urheber: {urheber}
Text (Vorblatt):
{text}
"""


class WrittenSummary(BaseModel):
    summary: str = Field(description="Ein bis zwei Sätze, höchstens 45 Wörter, auf Deutsch.")


class SummaryCheck(BaseModel):
    # The objections first: the verdict then follows from them.
    problems: list[str] = Field(
        default_factory=list, description="Jede unbelegte oder zugespitzte Aussage, kurz."
    )
    supported: bool = Field(description="True nur, wenn jede Aussage belegt ist.")


# (messages, schema) -> (parsed output, model name)
Call = Callable[[list[BaseMessage], type], Awaitable[tuple[Any, str]]]


@dataclass
class Document:
    number: str
    doc_type: str
    title: str
    urheber: list[str]
    text: str

    @property
    def source_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass
class SummaryReport:
    written: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    procedures: set[str] = field(default_factory=set)


def summarised_stages(record: ProcedureRecord) -> list[ProcedureStage]:
    """The Bundestag draft and committee reports of a law."""
    if record.kind != "legislation":
        return []
    return [
        s for s in record.stages
        if s.chamber == "BT" and s.document_kind == "Drucksache" and s.document_number
        and s.name.startswith(SUMMARISED_STAGES)
    ]


def read_document(qdrant: QdrantClient, collection: str, number: str) -> Optional[Document]:
    """The overview text of a stored Drucksache, in reading order."""
    points, _ = qdrant.scroll(
        collection_name=collection,
        scroll_filter=models.Filter(must=[
            models.FieldCondition(
                key="source_parent_key",
                match=models.MatchValue(value=f"{SourceType.DRUCKSACHE.value}:BT:{number}"),
            ),
            models.FieldCondition(key="doc_section", match=models.MatchValue(value="overview")),
        ]),
        limit=200,
        with_payload=["text", "chunk_index", "meta"],
        with_vectors=False,
    )
    if not points:
        return None
    payloads = sorted((p.payload or {} for p in points), key=lambda p: p.get("chunk_index", 0))
    meta = payloads[0].get("meta") or {}
    return Document(
        number=number,
        doc_type=str(meta.get("doc_type") or "Drucksache"),
        title=str(meta.get("title") or ""),
        urheber=[str(u) for u in meta.get("urheber") or []],
        text="\n\n".join(str(p.get("text") or "") for p in payloads)[:_MAX_TEXT_CHARS],
    )


async def summarise(doc: Document, call: Call) -> Optional[tuple[str, str]]:
    """(summary, model) once the check confirms it; None when it never does."""
    fields = {
        "doc_type": doc.doc_type, "title": doc.title,
        "urheber": ", ".join(doc.urheber) or "unbekannt", "text": doc.text,
    }
    feedback = ""
    for _ in range(2):
        written, model = await call(
            [HumanMessage(content=WRITE_PROMPT.format(feedback=feedback, **fields))], WrittenSummary
        )
        text = written.summary.strip()
        check, _ = await call(
            [HumanMessage(content=CHECK_PROMPT.format(summary=text, **fields))], SummaryCheck
        )
        if check.supported:
            return text, model
        logger.info("Summary of %s not supported: %s", doc.number, "; ".join(check.problems))
        feedback = (
            "\nEin früherer Entwurf wurde abgelehnt, weil: "
            + "; ".join(check.problems) + "\nVermeide das.\n"
        )
    return None


async def summarise_procedures(
    procedures: dict[str, ProcedureRecord],
    *,
    qdrant: QdrantClient,
    collection: str,
    call: Call,
    today: date,
    write: Callable[[str, dict[str, StepSummary]], None],
) -> SummaryReport:
    """Summarise the steps whose Drucksache is new or changed; ``write``
    stores a procedure's full summary map."""
    report = SummaryReport()
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(record: ProcedureRecord) -> None:
        current = dict(record.step_summaries)
        changed = False
        for stage in summarised_stages(record):
            number = stage.document_number or ""
            try:
                async with gate:
                    doc = await asyncio.to_thread(read_document, qdrant, collection, number)
                    if doc is None or not doc.text.strip():
                        continue
                    stored = current.get(number)
                    # Unchanged text: keep the summary, or the rejection.
                    if stored is not None and stored.source_hash == doc.source_hash:
                        continue
                    result = await summarise(doc, call)
            except Exception:  # noqa: BLE001 (one document never stops the run)
                logger.exception("Summary of %s failed", number)
                report.failed.append(number)
                continue
            text, model = result if result is not None else (None, "")
            if text is None:
                report.rejected.append(number)
            else:
                report.written.append(number)
            current[number] = StepSummary(
                text=text, document_number=number, source_hash=doc.source_hash,
                model=model, written_on=today,
            )
            changed = True
        if changed:
            write(record.vorgang_id, current)
            report.procedures.add(record.vorgang_id)

    await asyncio.gather(*(one(r) for r in procedures.values()))
    return report
