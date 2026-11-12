# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import logging

import pytest

from ingestion.feed.builder import speeches_block
from ingestion.feed.items import debate_input_hash
from ingestion.feed.parliaments import party_display_for
from ingestion.feed.reader import AgendaItem, Speech, assemble_speeches
from ingestion.feed.speaker_parties import (
    NON_PARTISAN,
    OutsideSpeaker,
    PartyResolver,
    Roster,
    load_roster,
)
from ingestion.party_slugs import CANONICAL_PARTY_SLUGS
from tests.feed.samples import speech as speech_payload

_PRIEN = OutsideSpeaker(
    name="Karin Prien",
    party="CDU",
    office="Bundesministerin für Bildung, Familie, Senioren, Frauen und Jugend",
    institution="Bundesregierung",
    redner_ids=("999990152",),
)
_WILDBERGER = OutsideSpeaker(
    name="Karsten Wildberger",
    party="CDU",
    office="Bundesminister für Digitales und Staatsmodernisierung",
    institution="Bundesregierung",
)
_NO_PARTY = OutsideSpeaker(
    name="Ronald Rauhe",
    party=None,
    office="Staatsminister für Sport und Ehrenamt",
    institution="Bundesregierung",
)


def _speech(speaker: str, party: str, **facts: object) -> Speech:
    [built] = assemble_speeches(
        [speech_payload("s1", speaker=speaker, party=party, text="Rede.")]
    )
    for key, value in facts.items():
        setattr(built, key, value)
    return built


def _resolver(stammdaten: dict[str, str] | None = None) -> PartyResolver:
    return PartyResolver(
        roster=Roster([_PRIEN, _WILDBERGER, _NO_PARTY]),
        stammdaten=lambda: stammdaten or {},
    )


def test_a_minister_from_outside_the_bundestag_is_filed_under_her_party() -> None:
    speech = _speech(
        "Karin Prien", "unbekannt", mdb_id="999990152", role="Bundesministerin BMBFSFJ"
    )
    _resolver()(speech)
    assert speech.party_id == "cdu"
    assert speech.reattributed_from == "unbekannt"
    # The protocol's own wording of the office wins over the roster's.
    assert speech.role == "Bundesministerin BMBFSFJ"


def test_the_roster_also_finds_a_speaker_by_name_and_supplies_the_office() -> None:
    speech = _speech("Dr. Karsten Wildberger", "unbekannt")
    _resolver()(speech)
    assert speech.party_id == "cdu"
    assert speech.role == _WILDBERGER.office


def test_the_protocols_fraktion_comes_first() -> None:
    speech = _speech("Anna Berg", "unbekannt", protocol_fraktion="SPD")
    _resolver({"11000001": "CDU"})(speech)
    assert speech.party_id == "spd"


def test_a_member_resolves_through_the_stammdaten_by_their_redner_id() -> None:
    speech = _speech("Christoph de Vries", "unbekannt", mdb_id="11004926")
    _resolver({"11004926": "CDU"})(speech)
    assert speech.party_id == "cdu"


def test_a_known_party_is_kept_and_a_disagreeing_protocol_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    speech = _speech("Anna Berg", "spd", protocol_fraktion="AfD")
    with caplog.at_level(logging.WARNING):
        _resolver()(speech)
    assert speech.party_id == "spd"
    assert speech.reattributed_from is None
    assert "protocol says afd" in caplog.text


def test_the_union_counts_as_one_fraktion() -> None:
    speech = _speech("Anna Berg", "csu", protocol_fraktion="CDU/CSU")
    _resolver()(speech)
    assert speech.party_id == "csu"


def test_an_unknown_speaker_stays_unbekannt_and_is_named_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    speech = _speech("Erika Gast", "unbekannt")
    with caplog.at_level(logging.WARNING):
        _resolver()(speech)
    assert speech.party_id == "unbekannt"
    assert speech.reattributed_from is None
    assert "Erika Gast" in caplog.text


def test_a_roster_speaker_without_a_party_gets_the_office_but_stays_unbekannt(
    caplog: pytest.LogCaptureFixture,
) -> None:
    speech = _speech("Ronald Rauhe", "unbekannt")
    with caplog.at_level(logging.WARNING):
        _resolver()(speech)
    assert speech.party_id == "unbekannt"
    assert speech.reattributed_from is None
    assert speech.role == _NO_PARTY.office
    assert caplog.text == ""


def test_only_a_moved_speech_changes_the_debates_input_hash() -> None:
    speech = _speech("Karin Prien", "unbekannt")
    item = AgendaItem(key="k", label="TOP 1", speeches=[speech])
    before = debate_input_hash(item)
    _resolver({})(_speech("Anna Berg", "spd"))
    assert debate_input_hash(item) == before
    _resolver()(speech)
    assert debate_input_hash(item) != before


def test_the_prompt_names_the_office_a_minister_spoke_in() -> None:
    speech = _speech("Karin Prien", "cdu", role="Bundesministerin BMBFSFJ")
    assert "Karin Prien (cdu, Bundesministerin BMBFSFJ):" in speeches_block([speech])


def test_every_roster_party_is_a_known_slug() -> None:
    known = set(CANONICAL_PARTY_SLUGS.values()) | {NON_PARTISAN}
    for outside in load_roster().speakers:
        assert outside.party is None or outside.party_slug in known, outside
    assert party_display_for(NON_PARTISAN, {}).name == "Parteilos"


def _unreadable_stammdaten() -> dict[str, str]:
    raise OSError("bundestag.de unreachable")


def test_without_the_stammdaten_an_open_speech_is_not_settled() -> None:
    resolver = PartyResolver(roster=Roster([_PRIEN]), stammdaten=_unreadable_stammdaten)
    member = _speech("Christoph de Vries", "unbekannt", mdb_id="11004926")
    assert resolver(member) is False
    assert member.party_id == "unbekannt"
    assert member.reattributed_from is None


def test_without_the_stammdaten_the_protocol_and_a_known_party_still_settle() -> None:
    resolver = PartyResolver(roster=Roster([]), stammdaten=_unreadable_stammdaten)
    named = _speech("Anna Berg", "unbekannt", protocol_fraktion="SPD")
    known = _speech("Bernd Roth", "afd")
    assert resolver(named) is True
    assert named.party_id == "spd"
    assert resolver(known) is True


def test_a_roster_office_is_not_given_to_a_speech_from_before_it() -> None:
    from datetime import date

    minister = OutsideSpeaker(
        name="Alexander Schweitzer",
        party="SPD",
        office="Bundesminister für Arbeit und Soziales",
        institution="Bundesregierung",
        redner_ids=("999990149",),
        valid_from=date(2026, 10, 13),
    )
    resolver = PartyResolver(roster=Roster([minister]), stammdaten=lambda: {})
    before = _speech("Alexander Schweitzer", "unbekannt", day=date(2026, 3, 5))
    after = _speech("Alexander Schweitzer", "unbekannt", day=date(2026, 10, 14))
    resolver(before)
    resolver(after)
    assert (before.party_id, before.role) == ("spd", None)
    assert (after.party_id, after.role) == ("spd", minister.office)


def test_every_roster_entry_names_its_sources_and_its_redner_id() -> None:
    import json

    from ingestion.feed.speaker_parties import ROSTER_PATH

    rows = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))["speakers"]
    for row in rows:
        assert row["redner_ids"], row["name"]
        assert row["office_source_url"].startswith("https://"), row["name"]
    # load_roster refuses an entry without its sources.
    assert len(load_roster().speakers) == len(rows)


def test_an_entry_without_its_sources_is_refused(tmp_path) -> None:
    import json

    path = tmp_path / "roster.json"
    path.write_text(
        json.dumps(
            {
                "speakers": [
                    {
                        "name": "Erika Gast",
                        "party": "cdu",
                        "office": "Bundesministerin",
                        "institution": "Bundesregierung",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="Erika Gast"):
        load_roster(path)
