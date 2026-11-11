# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pytest

from ingestion.feed import politicians as p
from ingestion.feed.models import DebateFacts, DebateParty, DigestSpeaker, FeedItem

NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)

_STAMMDATEN = """<?xml version="1.0" encoding="UTF-8"?>
<DOCUMENT>
  <MDB>
    <ID>11005000</ID>
    <NAMEN>
      <NAME><NACHNAME>Alt</NACHNAME><VORNAME>Sanae</VORNAME><AKAD_TITEL/>
        <HISTORIE_VON>26.10.2021</HISTORIE_VON><HISTORIE_BIS>01.01.2022</HISTORIE_BIS></NAME>
      <NAME><NACHNAME>Abdi</NACHNAME><VORNAME>Sanae</VORNAME><AKAD_TITEL>Dr.</AKAD_TITEL>
        <HISTORIE_VON>02.01.2022</HISTORIE_VON><HISTORIE_BIS/></NAME>
    </NAMEN>
    <BIOGRAFISCHE_ANGABEN>
      <GEBURTSDATUM>07.07.1986</GEBURTSDATUM>
      <BERUF>Vertragsmanagerin</BERUF>
      <PARTEI_KURZ>SPD</PARTEI_KURZ>
    </BIOGRAFISCHE_ANGABEN>
    <WAHLPERIODEN>
      <WAHLPERIODE><WP>21</WP><MDBWP_VON>25.03.2025</MDBWP_VON><MDBWP_BIS/>
        <INSTITUTIONEN>
          <INSTITUTION><INSART_LANG>Fraktion/Gruppe</INSART_LANG>
            <INS_LANG>Fraktion der SPD</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Vorstandsmitglied</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Ministerium</INSART_LANG>
            <INS_LANG>Bundesministerium der Finanzen</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Parlamentarische Staatssekretärin</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Deutscher Bundestag</INSART_LANG>
            <INS_LANG>Ältestenrat</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Ordentliches Mitglied</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Ausschuss</INSART_LANG>
            <INS_LANG>Haushaltsausschuss</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Obfrau</FKT_LANG><FKTINS_BIS/></INSTITUTION>
          <INSTITUTION><INSART_LANG>Fraktion/Gruppe</INSART_LANG>
            <INS_LANG>Fraktion der SPD</INS_LANG><MDBINS_BIS/>
            <FKT_LANG>Justiziarin</FKT_LANG><FKTINS_BIS>01.06.2025</FKTINS_BIS></INSTITUTION>
        </INSTITUTIONEN>
      </WAHLPERIODE>
      <WAHLPERIODE><WP>20</WP><MDBWP_VON>26.10.2021</MDBWP_VON>
        <MDBWP_BIS>25.03.2025</MDBWP_BIS></WAHLPERIODE>
    </WAHLPERIODEN>
  </MDB>
  <MDB>
    <ID>11001478</ID>
    <NAMEN><NAME><NACHNAME>Merkel</NACHNAME><VORNAME>Angela</VORNAME>
      <AKAD_TITEL>Dr.</AKAD_TITEL><HISTORIE_BIS/></NAME></NAMEN>
    <BIOGRAFISCHE_ANGABEN><GEBURTSDATUM>17.07.1954</GEBURTSDATUM>
      <PARTEI_KURZ>CDU</PARTEI_KURZ></BIOGRAFISCHE_ANGABEN>
    <WAHLPERIODEN><WAHLPERIODE><WP>19</WP><MDBWP_VON>24.10.2017</MDBWP_VON>
      <MDBWP_BIS>26.10.2021</MDBWP_BIS></WAHLPERIODE></WAHLPERIODEN>
  </MDB>
</DOCUMENT>"""

_INDEX = """<?xml version='1.0' encoding='UTF-8'?>
<mdbUebersicht><mdbs>
  <mdb fraktion="AfD"><mdbID status="Aktiv">9999</mdbID>
    <mdbName status="Aktiv">Abdi, Sanae</mdbName>
    <changedDateTime>01.10.2026 09:00</changedDateTime></mdb>
  <mdb fraktion="SPD"><mdbID status="Aktiv">2314</mdbID>
    <mdbName status="Aktiv">Abdi, Sanae</mdbName>
    <changedDateTime>07.10.2026 14:32</changedDateTime></mdb>
</mdbs></mdbUebersicht>"""

_ANGABEN = """<h3>Berufliche Tätigkeit vor der Mitgliedschaft im Deutschen Bundestag</h3>
<ul class="voa_list bt-liste">
 <li>Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH, Bonn,
 </li><li>Projekt- und Finanzmanagerin, Rückkehrrecht
</li></ul>
<p><br/></p>
<h3>Entgeltliche Tätigkeiten neben dem Mandat</h3>
<ul class="voa_list bt-liste">
 <li>Publizistische Tätigkeit
  <ul class="bt-liste">
   <li>Aufbau Verlage GmbH &amp; Co. KG, Berlin
   </li><li>2026:\xa010.321,53\xa0EUR, Brutto
  </li></ul>
</li></ul>
<p></p>
<ul class="voa_list bt-liste">
 <li>Vortragstätigkeiten
</li></ul>"""


def _profile(bio_id: str = "2314", born: str = "07.07.1986") -> str:
    return f"""<?xml version='1.0' encoding='UTF-8'?>
<mdb><dokumentInfo><dokumentStand>01.04.2025</dokumentStand></dokumentInfo>
<mdbInfo>
  <mdbID status="Aktiv">{bio_id}</mdbID>
  <mdbGeburtsdatum>{born}</mdbGeburtsdatum>
  <mdbBeruf berufsfeld="">Vertrags- und Finanzmanagerin</mdbBeruf>
  <mdbFraktion>SPD</mdbFraktion><mdbPartei>SPD</mdbPartei>
  <mdbLand>Nordrhein-Westfalen</mdbLand>
  <mdbWahlkreis><mdbWahlkreisNummer>092</mdbWahlkreisNummer>
    <mdbWahlkreisName>Köln I</mdbWahlkreisName></mdbWahlkreis>
  <mdbGewaehlt>direkt</mdbGewaehlt>
  <mdbBioURL>https://www.bundestag.de/abgeordnete/biografien/A/abdi_sanae-1043330</mdbBioURL>
  <mdbMitgliedschaften>
    <mdbObleuteGremien title="Obfrau">
      <mdbObleuteGremium id="a19"><gremiumName>Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung</gremiumName>
        <gremiumURL>https://www.bundestag.de/ausschuesse/entwicklung</gremiumURL></mdbObleuteGremium>
    </mdbObleuteGremien>
    <mdbOrdentlichesMitgliedGremien title="Ordentliches Mitglied">
      <mdbOrdentlichesMitgliedGremium id="a19"><gremiumName>Ausschuss für wirtschaftliche Zusammenarbeit und Entwicklung</gremiumName></mdbOrdentlichesMitgliedGremium>
      <mdbOrdentlichesMitgliedGremium id="pbne"><gremiumName>Parlamentarischer Beirat für nachhaltige Entwicklung und Zukunftsfragen</gremiumName></mdbOrdentlichesMitgliedGremium>
    </mdbOrdentlichesMitgliedGremien>
    <mdbStellvVorsitzSonstigeGremien title="Stellvertretende Vorsitzende">
      <mdbStellvVorsitzSonstigesGremium id="Parlamentariergruppe Maghreb-Staaten"><gremiumName>Parlamentariergruppe Maghreb-Staaten</gremiumName></mdbStellvVorsitzSonstigesGremium>
    </mdbStellvVorsitzSonstigeGremien>
  </mdbMitgliedschaften>
  <mdbVeroeffentlichungspflichtigeAngaben><![CDATA[{_ANGABEN}]]></mdbVeroeffentlichungspflichtigeAngaben>
  <mdbVeroeffentlichungspflichtigeAngabenLink>https://www.sanae-abdi.de/</mdbVeroeffentlichungspflichtigeAngabenLink>
  <mdbVeroeffentlichungspflichtigeAngabenLinkPhrase>Individuelle Erläuterungen</mdbVeroeffentlichungspflichtigeAngabenLinkPhrase>
</mdbInfo>
<mdbMedien><mdbFoto>
  <mdbFotoGrossURL>https://www.bundestag.de/resource/image/abdi_sanae.jpg</mdbFotoGrossURL>
  <mdbFotoCopyright>Sanae Abdi/SPD-Fraktion</mdbFotoCopyright>
</mdbFoto></mdbMedien></mdb>"""


@pytest.fixture
def stammdaten(tmp_path: Path) -> Path:
    path = tmp_path / "MDB_STAMMDATEN.XML"
    path.write_text(_STAMMDATEN, encoding="utf-8")
    return path


class FakeSnapshot:
    def __init__(self, doc_id: str, data: Optional[dict]) -> None:
        self.id = doc_id
        self.exists = data is not None
        self._data = data

    def to_dict(self) -> Optional[dict]:
        return self._data


class FakeRef:
    def __init__(self, db: "FakeDb", doc_id: str) -> None:
        self._db = db
        self.id = doc_id

    def set(self, data: dict) -> None:
        self._db.docs[self.id] = data


class FakeDb:
    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def collection(self, name: str) -> Any:
        assert name == p.POLITICIAN_COLLECTION
        return self

    def document(self, doc_id: str) -> FakeRef:
        return FakeRef(self, doc_id)

    def get_all(self, refs: list[FakeRef]) -> list[FakeSnapshot]:
        return [FakeSnapshot(r.id, self.docs.get(r.id)) for r in refs]


def _fetcher(pages: dict[str, str], log: Optional[list[str]] = None) -> p.Fetch:
    def fetch(url: str) -> str:
        if log is not None:
            log.append(url)
        if url not in pages:
            raise OSError(f"unreachable: {url}")
        return pages[url]

    return fetch


_VOTES = """<table class="e-table"><thead class="sr-only"><tr>
  <th>Datum</th><th>Titel Abstimmung</th><th>Abstimmungsverhalten</th></tr></thead>
<tbody class="e-table__body">
  <tr class="e-table__row"><td class="e-table__data">15.10.2026</td>
    <td class="e-table__data --break-word"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1037">Änderung des
      Brennstoffemissionshandelsgesetzes</a></td>
    <td class="e-table__data"><span class="a-vote --yes">ja</span></td></tr>
  <tr class="e-table__row"><td class="e-table__data">08.10.2026</td>
    <td class="e-table__data"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1033">Antrag zur
      Kassenzulassung des nicht-invasiven Pränataltests</a></td>
    <td class="e-table__data"><span class="a-vote --abstain">enthalten</span></td></tr>
  <tr class="e-table__row"><td class="e-table__data">08.10.2026</td>
    <td class="e-table__data"><a class="a-link"
      href="/parlament/plenum/abstimmung/abstimmung/?id=1027">Cum-Cum</a></td>
    <td class="e-table__data"><span class="a-vote --absent">nicht abg.</span></td></tr>
</tbody></table>"""


def _roll_call_list(newest: str = "15. Oktober 2026") -> str:
    return f"<div><p>{newest}</p><p>Änderung des Brennstoffemissionshandelsgesetzes</p></div>"


def _pages(newest: str = "15. Oktober 2026", **profiles: str) -> dict[str, str]:
    """The index, the roll-call list, and these profiles; the namesake's is
    always there, and the votes of the member's own profile."""
    profiles = {"9999": _profile("9999", "01.01.1970"), **profiles}
    return {
        p.INDEX_URL: _INDEX,
        p.ROLL_CALL_LIST_URL: _roll_call_list(newest),
        p.VOTES_URL.format(bio_id="2314"): _VOTES,
        **{p.PROFILE_URL.format(bio_id=k): v for k, v in profiles.items()},
    }


def _refresh(
    db: FakeDb, ids: list[str], stammdaten: Path, fetch: p.Fetch, **kwargs: Any
) -> p.RefreshReport:
    return p.refresh_politicians(
        db,
        ids,
        fetch=fetch,
        stammdaten=lambda due: p.read_stammdaten(stammdaten, due),
        now=kwargs.pop("now", NOW),
        pause=lambda: None,
        **kwargs,
    )


def test_the_stammdaten_give_name_terms_and_current_offices(stammdaten: Path) -> None:
    profile = p.read_stammdaten(stammdaten, ["11005000"])["11005000"]
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
    profile = p.parse_profile(_profile())
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
    assert profile.wahlkreis == p.Wahlkreis(number="092", name="Köln I")
    assert profile.photo_credit == "Sanae Abdi/SPD-Fraktion"


def test_the_disclosures_are_kept_verbatim_in_their_structure() -> None:
    disclosures = p.parse_profile(_profile()).disclosures
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
    disclosures = p.parse_disclosures(
        '<p class="taet_abstand_unten">Keine veröffentlichungspflichtigen Angaben.</p>'
    )
    assert disclosures is not None
    assert disclosures.sections == []
    assert disclosures.note == "Keine veröffentlichungspflichtigen Angaben."
    assert p.parse_disclosures("  ") is None


def test_a_namesake_is_told_apart_by_birth_date(stammdaten: Path) -> None:
    db = FakeDb()
    log: list[str] = []
    fetch = _fetcher(_pages(**{"2314": _profile()}), log)
    report = _refresh(db, ["11005000"], stammdaten, fetch)
    # The namesake comes first in the index and is ruled out.
    assert log == [
        p.INDEX_URL,
        p.ROLL_CALL_LIST_URL,
        p.PROFILE_URL.format(bio_id="9999"),
        p.PROFILE_URL.format(bio_id="2314"),
        p.VOTES_URL.format(bio_id="2314"),
    ]
    assert report.written == ["11005000"]
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert stored.bio_id == "2314"
    assert stored.last_changed == "07.10.2026 14:32"
    assert stored.offices[0].function == "Parlamentarische Staatssekretärin"
    assert stored.disclosures is not None


def test_an_unreadable_namesake_does_not_hide_the_right_profile(
    stammdaten: Path,
) -> None:
    pages = _pages(**{"2314": _profile()})
    del pages[p.PROFILE_URL.format(bio_id="9999")]
    db = FakeDb()
    assert _refresh(db, ["11005000"], stammdaten, _fetcher(pages)).written == [
        "11005000"
    ]
    assert db.docs["11005000"]["bio_id"] == "2314"


def test_an_unchanged_profile_is_not_fetched_again(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": _profile()})))
    log: list[str] = []
    report = _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(), log))
    assert report.written == []
    assert log == [p.INDEX_URL, p.ROLL_CALL_LIST_URL]


def test_a_changed_profile_is_fetched_by_its_known_id(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": _profile()})))
    db.docs["11005000"]["last_changed"] = "01.01.2026 00:00"
    log: list[str] = []
    fetch = _fetcher(_pages(**{"2314": _profile()}), log)
    assert _refresh(db, ["11005000"], stammdaten, fetch).written == ["11005000"]
    assert log == [
        p.INDEX_URL,
        p.ROLL_CALL_LIST_URL,
        p.PROFILE_URL.format(bio_id="2314"),
        p.VOTES_URL.format(bio_id="2314"),
    ]


def test_a_former_member_is_stored_from_the_stammdaten_and_retried_monthly(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    assert _refresh(db, ["11001478"], stammdaten, _fetcher(_pages())).written == [
        "11001478"
    ]
    stored = p.Politician.model_validate(db.docs["11001478"])
    assert (stored.name, stored.bio_id, stored.memberships) == (
        "Angela Merkel",
        None,
        [],
    )
    assert [t.wp for t in stored.terms] == [19]
    soon = NOW + timedelta(days=1)
    later = NOW + p.UNMATCHED_RETRY
    assert (
        _refresh(db, ["11001478"], stammdaten, _fetcher(_pages()), now=soon).written
        == []
    )
    assert _refresh(
        db, ["11001478"], stammdaten, _fetcher(_pages()), now=later
    ).written == ["11001478"]


def test_speakers_outside_the_stammdaten_and_failures_are_skipped(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    # Their profile cannot be fetched: logged, not raised, retried next run.
    report = _refresh(db, ["99999999", "11005000"], stammdaten, _fetcher(_pages()))
    assert report.not_members == ["99999999"]
    assert report.failed == ["11005000"]
    assert db.docs == {}


def test_a_spent_budget_stops_between_members(stammdaten: Path) -> None:
    report = _refresh(
        FakeDb(),
        ["11005000"],
        stammdaten,
        _fetcher(_pages(**{"2314": _profile()})),
        out_of_time=lambda: True,
    )
    assert report.out_of_time
    assert report.written == []


def test_speaker_ids_come_from_every_debate_once() -> None:
    def item(item_id: str, *ids: Optional[str]) -> FeedItem:
        return FeedItem.model_construct(
            id=item_id,
            debate=DebateFacts.model_construct(
                parties=[
                    DebateParty.model_construct(
                        speakers=[DigestSpeaker(name=f"n{i}", mdb_id=i) for i in ids]
                    )
                ]
            ),
        )

    items = [
        item("a", "1", None, "2"),
        item("b", "2", "3"),
        FeedItem.model_construct(debate=None),
    ]
    assert p.speaker_ids(items) == ["1", "2", "3"]


def test_the_votes_are_kept_as_listed_on_the_profile() -> None:
    votes = p.parse_roll_calls(_VOTES)
    assert [(v.day, v.vote, v.label) for v in votes] == [
        (date(2026, 10, 15), "yes", "ja"),
        (date(2026, 10, 8), "abstain", "enthalten"),
        (date(2026, 10, 8), "absent", "nicht abg."),
    ]
    assert votes[0].title == "Änderung des Brennstoffemissionshandelsgesetzes"
    assert votes[0].url == (
        "https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung/?id=1037"
    )


def test_a_newer_vote_refreshes_only_the_votes(stammdaten: Path) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": _profile()})))
    assert len(db.docs["11005000"]["votes"]) == 3

    # A vote the morning after the stored list was read.
    morning = datetime(2026, 11, 13, 6, tzinfo=timezone.utc)
    log: list[str] = []
    fetch = _fetcher(_pages("12. November 2026"), log)
    report = _refresh(db, ["11005000"], stammdaten, fetch, now=morning)
    assert report.written == ["11005000"]
    assert log == [
        p.INDEX_URL,
        p.ROLL_CALL_LIST_URL,
        p.VOTES_URL.format(bio_id="2314"),
    ]
    stored = p.Politician.model_validate(db.docs["11005000"])
    assert stored.votes_checked_at == morning
    # The rest of the record stays as read.
    assert stored.fetched_at == NOW

    # Read since that vote: nothing to do the next day.
    next_day = morning + timedelta(days=1)
    fetch = _fetcher(_pages("12. November 2026"))
    assert _refresh(db, ["11005000"], stammdaten, fetch, now=next_day).written == []


def test_an_unreadable_vote_list_falls_back_to_the_votes_age(
    stammdaten: Path,
) -> None:
    db = FakeDb()
    _refresh(db, ["11005000"], stammdaten, _fetcher(_pages(**{"2314": _profile()})))
    pages = _pages()
    del pages[p.ROLL_CALL_LIST_URL]
    soon = NOW + timedelta(days=1)
    later = NOW + p.VOTES_FALLBACK_AGE
    assert (
        _refresh(db, ["11005000"], stammdaten, _fetcher(pages), now=soon).written == []
    )
    assert _refresh(
        db, ["11005000"], stammdaten, _fetcher(pages), now=later
    ).written == ["11005000"]
