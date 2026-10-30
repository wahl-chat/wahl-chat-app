"""The Stimmt's? exporter's pure parts: vote counts, Drucksachen, ids."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from stimmts.drucksachen import (  # noqa: E402
    committee_genitive,
    document,
    number_from_url,
    submitter,
)
from stimmts.export import slugify  # noqa: E402
from stimmts.votes import pattern, tally_parties, vote_problems  # noqa: E402

FRACTIONS = {
    "linke": {"id": 1, "label": "Die Linke (Bundestag 2025 - 2029)"},
    "spd": {"id": 2, "label": "SPD (Bundestag 2025 - 2029)"},
    "gruene": {"id": 3, "label": "BÜNDNIS 90/­DIE GRÜNEN (Bundestag 2025 - 2029)"},
    "cdu": {"id": 4, "label": "CDU/CSU (Bundestag 2025 - 2029)"},
    "afd": {"id": 5, "label": "AfD (Bundestag 2025 - 2029)"},
    "none": {"id": 6, "label": "fraktionslos (Bundestag 2025 - 2029)"},
}


def votes(**counts: dict[str, int]) -> list[dict]:
    """Per-member votes: votes(spd={"yes": 2, "no": 1}) and so on."""
    return [
        {"fraction": FRACTIONS[party], "vote": vote}
        for party, by_vote in counts.items()
        for vote, n in by_vote.items()
        for _ in range(n)
    ]


class TestTallyParties:
    def test_counts_each_fraktion_in_seating_order(self):
        parties, unaffiliated = tally_parties(
            votes(
                afd={"no": 3, "no_show": 1},
                spd={"yes": 4},
                linke={"no": 2},
                gruene={"abstain": 2, "no": 1},
                cdu={"yes": 5},
                none={"yes": 1, "no_show": 2},
            )
        )
        assert [p["partyId"] for p in parties] == [
            "linke",
            "spd",
            "gruene",
            "cdu",
            "afd",
        ]
        assert [p["answer"] for p in parties] == ["no", "yes", "abstain", "yes", "no"]
        assert parties[4] == {
            "partyId": "afd",
            "answer": "no",
            "yes": 0,
            "no": 3,
            "abstain": 0,
            "noShow": 1,
            "unity": 1.0,
        }
        assert unaffiliated == 3
        assert pattern(parties) == "NJEJN"

    def test_finds_the_greens_despite_the_soft_hyphen(self):
        parties, _ = tally_parties(votes(gruene={"yes": 3}))
        assert parties[2]["yes"] == 3

    def test_flags_a_split_party_and_a_short_chamber(self):
        parties, unaffiliated = tally_parties(votes(spd={"yes": 6, "no": 4}))
        problems = vote_problems(parties, unaffiliated)
        assert any(p.startswith("spd is split") for p in problems)
        assert "the seats add up to 10, not 630" in problems


class TestDrucksachen:
    BILL = {
        "dokumentnummer": "21/6278",
        "drucksachetyp": "Gesetzentwurf",
        "datum": "2026-06-08",
        "titel": "Entwurf eines Gesetzes zur Änderung\r\n des Gebäudeenergiegesetzes",
        "urheber": [{"titel": "Bundesregierung"}],
        "fundstelle": {
            "pdf_url": "https://dserver.bundestag.de/btd/21/062/2106278.pdf"
        },
    }
    RECOMMENDATION = {
        "dokumentnummer": "21/7009",
        "drucksachetyp": "Beschlussempfehlung und Bericht",
        "urheber": [{"titel": "Ausschuss für Wirtschaft und Energie"}],
        "fundstelle": {
            "pdf_url": "https://dserver.bundestag.de/btd/21/070/2107009.pdf"
        },
    }

    def test_reads_the_number_from_a_pdf_link(self):
        assert (
            number_from_url("https://dserver.bundestag.de/btd/21/062/2106278.pdf")
            == "21/6278"
        )
        assert (
            number_from_url("https://dserver.bundestag.de/btd/21/001/2100042.pdf")
            == "21/42"
        )
        assert number_from_url("https://example.org/file.pdf") is None

    def test_names_the_submitter_as_the_cover_prints_it(self):
        assert submitter({"urheber": [{"titel": "Bundesregierung"}]})[0] == {
            "initiator": "der Bundesregierung"
        }
        assert submitter({"urheber": [{"titel": "Bundesrat"}]})[0] == {
            "initiator": "des Bundesrates"
        }
        motion = {
            "urheber": [{"titel": "Fraktion BÜNDNIS 90/DIE GRÜNEN"}],
            "autoren_anzeige": [
                {"autor_titel": "Rebecca Lenhard"},
                {"autor_titel": "Dr. Konstantin von Notz"},
            ],
            "autoren_anzahl": 14,
        }
        assert submitter(motion) == (
            {
                "fraktion": "BÜNDNIS 90/DIE GRÜNEN",
                "members": ["Rebecca Lenhard", "Dr. Konstantin von Notz"],
                "memberCount": 14,
            },
            [],
        )
        assert submitter({"urheber": [{"titel": "Fraktion der AfD"}]})[0] == {
            "initiator": "der Fraktion der AfD"
        }

    def test_flags_what_it_cannot_word_with_certainty(self):
        joint, notes = submitter(
            {
                "urheber": [
                    {"titel": "Fraktion der CDU/CSU"},
                    {"titel": "Fraktion der SPD"},
                ]
            }
        )
        assert joint == {"initiator": "der Fraktionen der CDU/CSU und der SPD"}
        assert notes
        assert (
            submitter({"urheber": [{"titel": "Bundesverfassungsgericht"}]})[0] is None
        )

    def test_puts_committees_in_the_genitive(self):
        assert committee_genitive("Ausschuss für Wirtschaft und Energie") == (
            "des Ausschusses für Wirtschaft und Energie"
        )
        assert committee_genitive("Haushaltsausschuss") == "des Haushaltsausschusses"
        assert committee_genitive("Bundesregierung") is None

    def test_builds_the_document_with_the_version_voted_on(self):
        found, notes = document([self.RECOMMENDATION, self.BILL])
        assert found == {
            "type": "Gesetzentwurf",
            "number": "21/6278",
            "date": "2026-06-08",
            "initiator": "der Bundesregierung",
            "title": "Entwurf eines Gesetzes zur Änderung des Gebäudeenergiegesetzes",
            "url": "https://dserver.bundestag.de/btd/21/062/2106278.pdf",
            "votedIn": {
                "label": "Beschlussempfehlung des Ausschusses für Wirtschaft und Energie",
                "number": "21/7009",
                "url": "https://dserver.bundestag.de/btd/21/070/2107009.pdf",
            },
        }
        assert notes == []

    def test_notes_when_several_bills_are_linked(self):
        second = {**self.BILL, "dokumentnummer": "21/6565"}
        found, notes = document([second, self.BILL])
        assert found["number"] == "21/6278"
        assert any("21/6565" in note for note in notes)

    def test_has_no_document_without_a_bill_or_motion(self):
        found, notes = document([self.RECOMMENDATION])
        assert found is None
        assert notes


def test_slugify_spells_out_umlauts_and_stays_short():
    assert (
        slugify("Änderung des Stromsteuer­gesetzes")
        == "aenderung-des-stromsteuergesetzes"
    )
    assert slugify("Straße für Öl & Gas") == "strasse-fuer-oel-gas"
    long = slugify(
        "Anpassung des nationalen Rechts an die Reform des Gemeinsamen Europäischen Asylsystems"
    )
    assert len(long) <= 60 and not long.endswith("-")
