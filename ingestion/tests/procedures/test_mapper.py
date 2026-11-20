# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from typing import Any

from ingestion.procedures.mapper import (
    NO_PARTY,
    build_record,
    party_ids_of,
    profile_chunk,
)
from ingestion.schemas import SourceType

TODAY = date(2026, 11, 17)


def _record(vorgaenge: dict[str, Any], positions: dict[str, Any], vid: str, **kw: Any):
    return build_record(
        vorgaenge[vid], positions.get(vid, []), previous=kw.get("previous"), today=TODAY
    )


def test_party_ids_from_fraktionen_and_gruppen_only() -> None:
    assert party_ids_of(
        [
            "Fraktion der CDU/CSU",
            "Fraktion der SPD",
            "Bundesregierung",
            "Gruppe Die Linke",
        ]
    ) == ["cdu", "linke", "spd"]
    assert party_ids_of(["Fraktion BÜNDNIS 90/DIE GRÜNEN"]) == ["gruene"]
    assert party_ids_of(["Haushaltsausschuss", "Bayern"]) == []


def test_the_schuldenbremse_law_keeps_its_decisive_vote(vorgaenge, positions) -> None:
    record = _record(vorgaenge, positions, "320784")
    assert record.kind == "legislation"
    assert record.stages == sorted(record.stages, key=lambda s: (s.date, s.position_id))
    third = [s for s in record.stages if s.name == "3. Beratung"]
    assert third and third[0].chamber == "BT"
    decision = third[0].decisions[0]
    assert decision.result == "512:206:0"
    assert decision.vote_kind == "Namentliche Abstimmung"
    assert decision.document_numbers == ["20/15096", "20/15117"]
    assert "20/15096" in record.drucksache_numbers
    assert record.initiative_party_ids == ["cdu", "spd"]


def test_protocol_stages_carry_page_and_link(vorgaenge, positions) -> None:
    record = _record(vorgaenge, positions, "338366")
    first = next(s for s in record.stages if s.name == "1. Beratung")
    assert first.document_kind == "Plenarprotokoll"
    assert first.document_number == "21/91"
    assert first.page and first.url and "#P." in first.url


def test_drucksachen_are_deduplicated_per_chamber(vorgaenge, positions) -> None:
    record = _record(vorgaenge, positions, "338366")
    keys = [(d.chamber, d.number) for d in record.drucksachen]
    assert len(keys) == len(set(keys))
    assert {"BR", "BT"} <= {d.chamber for d in record.drucksachen}
    assert all("/" in n and not n.endswith("/26") for n in record.drucksache_numbers)


def test_first_sight_dates_the_change_to_the_newest_stage(vorgaenge, positions) -> None:
    record = _record(vorgaenge, positions, "338366")
    assert record.stage_changed_on == record.latest_stage_on


def test_a_new_stage_moves_stage_changed_on_to_today(vorgaenge, positions) -> None:
    pos = positions["338366"]
    before = build_record(
        vorgaenge["338366"], pos[:-1], previous=None, today=date(2026, 11, 1)
    )
    after = build_record(vorgaenge["338366"], pos, previous=before, today=TODAY)
    assert after.stage_changed_on == TODAY
    assert after.content_hash != before.content_hash


def test_an_edit_without_a_new_stage_keeps_stage_changed_on(
    vorgaenge, positions
) -> None:
    pos = positions["338366"]
    before = build_record(
        vorgaenge["338366"], pos, previous=None, today=date(2026, 11, 1)
    )
    edited = {
        **vorgaenge["338366"],
        "beratungsstand": "Verabschiedet",
        "aktualisiert": "x",
    }
    after = build_record(edited, pos, previous=before, today=TODAY)
    assert after.stage_changed_on == before.stage_changed_on
    assert after.content_hash != before.content_hash


def test_an_unchanged_resync_has_the_same_hash(vorgaenge, positions) -> None:
    a = _record(vorgaenge, positions, "338366")
    b = build_record(
        {**vorgaenge["338366"], "aktualisiert": "later"},
        positions["338366"],
        previous=a,
        today=TODAY,
    )
    assert a.content_hash == b.content_hash
    assert (
        profile_chunk(a, today=TODAY).content_hash
        == profile_chunk(b, today=date(2027, 1, 1)).content_hash
    )


def test_profile_chunk_names_topics_and_course(vorgaenge, positions) -> None:
    record = _record(vorgaenge, positions, "338366")
    chunk = profile_chunk(record, today=TODAY)
    assert chunk.source_type == SourceType.PROCEDURE
    assert chunk.vorgang_ids == ["338366"]
    assert "Haushaltsbegleitgesetz 2027" in chunk.text
    assert "Öffentliche Finanzen, Steuern und Abgaben" in chunk.text
    assert "1. Beratung" in chunk.text
    assert chunk.party_id == NO_PARTY  # a government bill belongs to no party
    assert chunk.source_parent_key == "procedure:338366"


def test_an_antrag_of_one_fraktion_is_that_partys(vorgaenge, positions) -> None:
    chunk = profile_chunk(_record(vorgaenge, positions, "341758"), today=TODAY)
    assert chunk.party_id == "linke"
    assert chunk.party_ids == ["linke"]


def test_profile_hash_covers_the_citation_title(vorgaenge, positions) -> None:
    a = _record(vorgaenge, positions, "341758")
    renamed = build_record(
        {**vorgaenge["341758"], "titel": "Anderer Titel"},
        positions["341758"],
        previous=None,
        today=TODAY,
    )
    assert (
        profile_chunk(a, today=TODAY).content_hash
        != profile_chunk(renamed, today=TODAY).content_hash
    )
