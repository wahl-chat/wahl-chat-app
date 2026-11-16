# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from ingestion.procedures.drucksachen import drucksache_chunks, split_sections, wanted_numbers
from ingestion.procedures.mapper import build_record
from ingestion.schemas import AuthorityTier, SourceType

from .conftest import load

TODAY = date(2026, 11, 17)


def test_a_bill_splits_into_vorblatt_articles_and_begruendung() -> None:
    doc = load("drucksache_21_7860")
    paths = [s.path for s in split_sections(doc["text"], doc["drucksachetyp"])]
    assert ("Vorblatt", "A. Problem und Ziel") in paths
    assert ("Gesetzestext", "Artikel 3") in paths
    assert ("Begründung", "B. Besonderer Teil", "Zu Artikel 3 (Änderung des Alkopopsteuergesetzes )") in paths
    assert ("Begründung", "A. Allgemeiner Teil", "VII. Gesetzesfolgen") in paths


def test_only_the_vorblatt_of_a_bill_is_overview() -> None:
    doc = load("drucksache_21_7860")
    sections = split_sections(doc["text"], doc["drucksachetyp"])
    assert {s.path[0] for s in sections if s.doc_section == "overview"} == {"Vorblatt"}


def test_a_committee_report_keeps_its_bericht_sections() -> None:
    doc = load("drucksache_21_8457")
    paths = [s.path for s in split_sections(doc["text"], doc["drucksachetyp"])]
    assert ("Bericht", "IV. Beratungsverlauf und Beratungsergebnisse im federführenden Ausschuss") in paths


def test_an_antrag_is_overview_throughout_and_its_fraktions() -> None:
    doc = load("drucksache_21_9233")
    chunks = drucksache_chunks(doc, procedures={}, mode="full", today=TODAY)
    assert chunks and {c.doc_section for c in chunks} == {"overview"}
    assert {c.party_id for c in chunks} == {"linke"}
    assert chunks[0].authority_tier == AuthorityTier.SELF_REPORTED


def test_chunks_carry_breadcrumb_procedure_and_size(vorgaenge, positions) -> None:
    procedures = {"338366": build_record(vorgaenge["338366"], positions["338366"], previous=None, today=TODAY)}
    chunks = drucksache_chunks(load("drucksache_21_7860"), procedures=procedures, mode="full", today=TODAY)
    first = chunks[0]
    assert first.text.startswith("Drucksache 21/7860 · Gesetzentwurf: Haushaltsbegleitgesetz 2027 · Vorblatt")
    assert first.source_type == SourceType.DRUCKSACHE
    assert first.vorgang_ids == ["338366"]
    assert first.party_id == "_all" and first.authority_tier == AuthorityTier.FACTUAL_RECORD
    assert first.source_parent_key == "drucksache:BT:21/7860"
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert max(len(c.text) for c in chunks) < 1500


def test_overview_mode_drops_the_body() -> None:
    doc = load("drucksache_21_7860")
    full = drucksache_chunks(doc, procedures={}, mode="full", today=TODAY)
    overview = drucksache_chunks(doc, procedures={}, mode="overview", today=TODAY)
    assert 0 < len(overview) < len(full)
    assert drucksache_chunks(doc, procedures={}, mode="off", today=TODAY) == []


def test_the_hash_is_stable_and_covers_the_procedure_link(vorgaenge, positions) -> None:
    doc = load("drucksache_21_7860")
    a = drucksache_chunks(doc, procedures={}, mode="overview", today=TODAY)
    b = drucksache_chunks(doc, procedures={}, mode="overview", today=date(2027, 1, 1))
    assert [c.content_hash for c in a] == [c.content_hash for c in b]
    procedures = {"338366": build_record(vorgaenge["338366"], positions["338366"], previous=None, today=TODAY)}
    c = drucksache_chunks(doc, procedures=procedures, mode="overview", today=TODAY)
    assert a[0].content_hash != c[0].content_hash


def test_wanted_numbers_are_readable_bt_documents(vorgaenge, positions) -> None:
    procedures = {"338366": build_record(vorgaenge["338366"], positions["338366"], previous=None, today=TODAY)}
    numbers = wanted_numbers(procedures)
    assert "21/7860" in numbers and "21/9241" in numbers
    assert not any(n.endswith("/26") for n in numbers)  # no Bundesrat papers
