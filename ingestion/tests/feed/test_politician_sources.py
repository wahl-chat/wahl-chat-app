# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from pathlib import Path

import pytest

from ingestion.feed import politician_sources as s
from tests.feed.politician_samples import VOTES, profile_xml, write_stammdaten


@pytest.fixture
def stammdaten(tmp_path: Path) -> Path:
    return write_stammdaten(tmp_path)


def test_the_stammdaten_give_name_terms_and_current_offices(stammdaten: Path) -> None:
    profile = s.read_stammdaten(stammdaten, ["11005000"])["11005000"]
    # The name in use now, not the earlier one.
    assert (profile.title, profile.name) == ("Dr.", "Sanae Abdi")
    assert profile.birth_date == date(1986, 7, 7)
    assert [t.wp for t in profile.terms] == [20, 21]
    assert profile.terms[0].start == date(2021, 10, 26)
    # Government first; a function that ended and a plain Gremium are left out.
    assert [(o.kind, o.function) for o in profile.offices] == [
        ("government", "Parlamentarische Staatssekretärin"),
        ("fraktion", "Vorstandsmitglied"),
    ]


def test_a_profile_keeps_each_role_as_published() -> None:
    profile = s.parse_profile(profile_xml())
    assert [(m.gremium[:20], m.role, m.level, m.kind) for m in profile.memberships] == [
        ("Ausschuss für wirtsc", "Obfrau", "spokesperson", "ausschuss"),
        ("Ausschuss für wirtsc", "Ordentliches Mitglied", "member", "ausschuss"),
        ("Parlamentarischer Be", "Ordentliches Mitglied", "member", "sonstige"),
        (
            "Parlamentariergruppe",
            "Stellvertretende Vorsitzende",
            "vice_chair",
            "sonstige",
        ),
    ]
    assert profile.wahlkreis == s.Wahlkreis(number="092", name="Köln I")
    assert profile.photo_credit == "Sanae Abdi/SPD-Fraktion"


def test_the_disclosures_are_kept_verbatim_in_their_structure() -> None:
    disclosures = s.parse_profile(profile_xml()).disclosures
    assert disclosures is not None
    assert disclosures.link == "https://www.sanae-abdi.de/"
    [before, paid] = disclosures.sections
    assert before.heading == (
        "Berufliche Tätigkeit vor der Mitgliedschaft im Deutschen Bundestag"
    )
    assert [[line.text for line in e.lines] for e in before.entries] == [
        [
            "Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH, Bonn,",
            "Projekt- und Finanzmanagerin, Rückkehrrecht",
        ]
    ]
    assert [[(line.text, line.level) for line in e.lines] for e in paid.entries] == [
        [
            ("Publizistische Tätigkeit", 0),
            ("Aufbau Verlage GmbH & Co. KG, Berlin", 1),
            ("2026: 10.321,53 EUR, Brutto", 1),
        ],
        [("Vortragstätigkeiten", 0)],
    ]


def test_a_member_without_disclosures_says_so() -> None:
    disclosures = s.parse_disclosures(
        '<p class="taet_abstand_unten">Keine veröffentlichungspflichtigen Angaben.</p>'
    )
    assert disclosures is not None
    assert disclosures.sections == []
    assert disclosures.note == "Keine veröffentlichungspflichtigen Angaben."
    assert s.parse_disclosures("  ") is None


def test_the_votes_are_kept_as_listed_on_theprofile() -> None:
    votes = s.parse_roll_calls(VOTES)
    assert [(v.day, v.vote, v.label) for v in votes] == [
        (date(2026, 10, 15), "yes", "ja"),
        (date(2026, 10, 8), "abstain", "enthalten"),
        (date(2026, 10, 8), "absent", "nicht abg."),
    ]
    assert votes[0].title == "Änderung des Brennstoffemissionshandelsgesetzes"
    assert votes[0].url == (
        "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung/?id=1037"
    )
