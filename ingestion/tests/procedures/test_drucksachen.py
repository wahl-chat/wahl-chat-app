# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any

import pytest

from ingestion.procedures import drucksachen
from ingestion.procedures.drucksachen import (
    drucksache_chunks,
    ingest_drucksachen,
    split_sections,
    wanted_numbers,
)
from ingestion.procedures.mapper import build_record
from ingestion.schemas import AuthorityTier, SourceType

from .conftest import load
from .fakes import FakeDip, FakeEmbed, FakeQdrant

TODAY = date(2026, 11, 17)


def test_a_bill_splits_into_vorblatt_articles_and_begruendung() -> None:
    doc = load("drucksache_21_7860")
    paths = [s.path for s in split_sections(doc["text"], doc["drucksachetyp"])]
    assert ("Vorblatt", "A. Problem und Ziel") in paths
    assert ("Gesetzestext", "Artikel 3") in paths
    assert (
        "Begründung",
        "B. Besonderer Teil",
        "Zu Artikel 3 (Änderung des Alkopopsteuergesetzes )",
    ) in paths
    assert ("Begründung", "A. Allgemeiner Teil", "VII. Gesetzesfolgen") in paths


def test_only_the_vorblatt_of_a_bill_is_overview() -> None:
    doc = load("drucksache_21_7860")
    sections = split_sections(doc["text"], doc["drucksachetyp"])
    assert {s.path[0] for s in sections if s.kind == "overview"} == {"Vorblatt"}


def test_a_committee_report_keeps_its_bericht_sections() -> None:
    doc = load("drucksache_21_8457")
    paths = [s.path for s in split_sections(doc["text"], doc["drucksachetyp"])]
    assert (
        "Bericht",
        "IV. Beratungsverlauf und Beratungsergebnisse im federführenden Ausschuss",
    ) in paths


def test_an_antrag_is_overview_throughout_and_its_fraktions() -> None:
    doc = load("drucksache_21_9233")
    chunks = drucksache_chunks(doc, procedures={}, today=TODAY)
    assert chunks and {c.doc_section for c in chunks} == {"overview"}
    assert {c.party_id for c in chunks} == {"linke"}
    assert chunks[0].authority_tier == AuthorityTier.SELF_REPORTED


def test_chunks_carry_breadcrumb_procedure_and_size(vorgaenge, positions) -> None:
    procedures = {
        "338366": build_record(
            vorgaenge["338366"], positions["338366"], previous=None, today=TODAY
        )
    }
    chunks = drucksache_chunks(
        load("drucksache_21_7860"), procedures=procedures, today=TODAY
    )
    first = chunks[0]
    assert first.text.startswith(
        "Drucksache 21/7860 · Gesetzentwurf: Haushaltsbegleitgesetz 2027 · Vorblatt"
    )
    assert first.source_type == SourceType.DRUCKSACHE
    assert first.vorgang_ids == ["338366"]
    assert (
        first.party_id == "_all"
        and first.authority_tier == AuthorityTier.FACTUAL_RECORD
    )
    assert first.source_parent_key == "drucksache:BT:21/7860"
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert max(len(c.text) for c in chunks) < 1500


def test_law_text_and_begruendung_never_become_chunks() -> None:
    doc = load("drucksache_21_7860")
    chunks = drucksache_chunks(doc, procedures={}, today=TODAY)
    assert chunks and {c.doc_section for c in chunks} == {"overview"}
    paths = {tuple(c.meta["section_path"]) for c in chunks}
    assert not any(p[0] in ("Gesetzestext", "Begründung") for p in paths)


def test_an_overlong_bill_still_yields_its_vorblatt(monkeypatch) -> None:
    import ingestion.procedures.drucksachen as module

    doc = load("drucksache_21_7860")
    overview = drucksache_chunks(doc, procedures={}, today=TODAY)
    monkeypatch.setattr(module, "MAX_TEXT_CHARS", len(doc["text"]) // 2)
    capped = drucksache_chunks(doc, procedures={}, today=TODAY)
    assert [c.text for c in capped] == [c.text for c in overview]


def test_the_hash_is_stable_and_covers_the_procedure_link(vorgaenge, positions) -> None:
    doc = load("drucksache_21_7860")
    a = drucksache_chunks(doc, procedures={}, today=TODAY)
    b = drucksache_chunks(doc, procedures={}, today=date(2027, 1, 1))
    assert [c.content_hash for c in a] == [c.content_hash for c in b]
    procedures = {
        "338366": build_record(
            vorgaenge["338366"], positions["338366"], previous=None, today=TODAY
        )
    }
    c = drucksache_chunks(doc, procedures=procedures, today=TODAY)
    assert a[0].content_hash != c[0].content_hash


def test_wanted_numbers_are_readable_bt_documents(vorgaenge, positions) -> None:
    procedures = {
        "338366": build_record(
            vorgaenge["338366"], positions["338366"], previous=None, today=TODAY
        )
    }
    numbers = wanted_numbers(procedures)
    assert "21/7860" in numbers and "21/9241" in numbers
    assert not any(n.endswith("/26") for n in numbers)  # no Bundesrat papers


def test_a_bill_in_paragraphs_leaves_the_vorblatt_at_its_law_title() -> None:
    text = "\n".join(
        [
            "Gesetzentwurf",
            "A. Problem und Ziel",
            "Ein Problem.",
            "B. Lösung",
            "Eine Lösung.",
            "F. Weitere Kosten",
            "Keine.",
            "Entwurf eines Gesetzes über das Beispielwesen",
            "Vom …",
            "§ 1",
            "Geltungsbereich",
            "Dieses Gesetz gilt.",
            "§ 2",
            "Begriffe",
            "Im Sinne dieses Gesetzes …",
            "Begründung",
            "A. Allgemeiner Teil",
            "Darum.",
        ]
    )
    sections = split_sections(text, "Gesetzentwurf")
    overview = [s for s in sections if s.kind == "overview"]
    assert all(s.path[0] == "Vorblatt" for s in overview)
    law = [s for s in sections if s.path[0] == "Gesetzestext"]
    assert law and law[0].kind == "body" and "Dieses Gesetz gilt." in law[0].text


def test_a_report_title_mentioning_a_bill_does_not_end_the_vorblatt() -> None:
    doc = load("drucksache_21_8457")
    sections = split_sections(doc["text"], doc["drucksachetyp"])
    assert ("Vorblatt", "A. Problem") in [s.path for s in sections]


def test_a_committee_bericht_is_the_report_and_read_by_default() -> None:
    doc = load("drucksache_21_8457")
    sections = split_sections(doc["text"], doc["drucksachetyp"])
    assert {s.kind for s in sections if s.path[0] == "Bericht"} == {"report"}
    assert {s.kind for s in sections if s.path[0] == "Beschlussempfehlung"} == {"body"}
    read = drucksache_chunks(doc, procedures={}, today=TODAY)
    assert {c.doc_section for c in read} == {"overview", "report"}


def test_a_document_that_cannot_be_chunked_fails_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def chunks(doc: dict[str, Any], **kw: Any) -> Any:
        if doc["dokumentnummer"] == "21/7860":
            raise ValueError("malformed text")
        return drucksache_chunks(doc, **kw)

    monkeypatch.setattr(drucksachen, "drucksache_chunks", chunks)
    dip = FakeDip(
        {},
        {},
        texts={
            "21/7860": load("drucksache_21_7860"),
            "21/9233": load("drucksache_21_9233"),
        },
    )
    qdrant = FakeQdrant()
    report = ingest_drucksachen(
        ["21/7860", "21/9233"],
        dip=dip,
        qdrant=qdrant,
        collection="c",
        embed=FakeEmbed(),
        procedures={},
        today=TODAY,
    )
    assert report.failed == ["21/7860"] and report.written == 1
    parents = {p["source_parent_key"] for p in qdrant.points.values()}
    assert parents == {"drucksache:BT:21/9233"}
