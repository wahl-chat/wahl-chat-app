# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for bundestag_speeches.parser.parse_speeches_from_xml.

Covers:
  - Normal speaker extraction (SPD, ID, name, party from XML <fraktion>)
  - Kommentar nodes skipped (not included in speech body text)
  - Merged-name speaker override from redner.tail visible label
  - Non-MdB speaker (ID starting with "999") extractable but flaggable
  - Billion-laughs / entity-expansion XML raises (defusedxml hardening)
"""

from __future__ import annotations

import pytest

from src.ingestion.connectors.bundestag_speeches.parser import (
    parse_speeches_from_xml,
)


# ---------------------------------------------------------------------------
# TestParserBasic — normal speaker, text extraction, kommentar skip
# ---------------------------------------------------------------------------


class TestParserBasic:
    """parse_speeches_from_xml extracts speaker/party/text from valid XML."""

    def test_returns_list(self, protocol_xml: str) -> None:
        """parse_speeches_from_xml returns a list of speech dicts."""
        result = parse_speeches_from_xml(protocol_xml)
        assert isinstance(result, list)

    def test_expected_speech_count(self, protocol_xml: str) -> None:
        """Protocol fixture has 3 <rede> nodes → 3 speech dicts returned."""
        result = parse_speeches_from_xml(protocol_xml)
        assert len(result) == 3

    def test_spd_speaker_name(self, protocol_xml: str) -> None:
        """First speech (Scholz / SPD) extracts correct speaker name."""
        result = parse_speeches_from_xml(protocol_xml)
        spd_speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004870"), None
        )
        assert spd_speech is not None, "SPD speech (id=11004870) not found"
        assert "Scholz" in spd_speech.get("speaker_name", "")

    def test_spd_speaker_party(self, protocol_xml: str) -> None:
        """First speech (Scholz / SPD) extracts correct party."""
        result = parse_speeches_from_xml(protocol_xml)
        spd_speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004870"), None
        )
        assert spd_speech is not None
        assert spd_speech.get("party") == "SPD"

    def test_spd_speech_text_nonempty(self, protocol_xml: str) -> None:
        """First speech body text is non-empty."""
        result = parse_speeches_from_xml(protocol_xml)
        spd_speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004870"), None
        )
        assert spd_speech is not None
        assert spd_speech.get("text"), "SPD speech text must not be empty"

    def test_kommentar_excluded_from_text(self, protocol_xml: str) -> None:
        """<kommentar> content (e.g. '(Beifall bei der SPD)') must not appear in speech text."""
        result = parse_speeches_from_xml(protocol_xml)
        spd_speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004870"), None
        )
        assert spd_speech is not None
        text = spd_speech.get("text", "")
        assert "Beifall" not in text, "Kommentar text must be excluded from speech body"

    def test_xml_rede_id_set(self, protocol_xml: str) -> None:
        """xml_rede_id must be extracted from the <rede id=...> attribute."""
        result = parse_speeches_from_xml(protocol_xml)
        spd_speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004870"), None
        )
        assert spd_speech is not None
        assert spd_speech.get("xml_rede_id") == "ID215000100"


# ---------------------------------------------------------------------------
# TestMergedNameSpeaker — merged structured name overridden by redner.tail
# ---------------------------------------------------------------------------


class TestMergedNameSpeaker:
    """Merged-name speaker (suspicious structured metadata) uses redner.tail label."""

    def test_merged_name_speaker_found(self, protocol_xml: str) -> None:
        """Baerbock speech (id=11004220) is present in the output."""
        result = parse_speeches_from_xml(protocol_xml)
        speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004220"), None
        )
        assert speech is not None, "Baerbock speech (id=11004220) not found"

    def test_merged_name_overridden_by_tail(self, protocol_xml: str) -> None:
        """Merged structured name (AnnalenaBarb+ock) is corrected via redner.tail label."""
        result = parse_speeches_from_xml(protocol_xml)
        speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004220"), None
        )
        assert speech is not None
        name = speech.get("speaker_name", "")
        # After tail override, the merged artifact 'AnnalenaBarb' must not appear
        assert "AnnalenaBarb" not in name, (
            f"Merged name artifact must be overridden by tail label; got: {name!r}"
        )

    def test_merged_name_party_resolved(self, protocol_xml: str) -> None:
        """Party for merged-name speaker resolves to 'BÜNDNIS 90/DIE GRÜNEN'."""
        result = parse_speeches_from_xml(protocol_xml)
        speech = next(
            (s for s in result if s.get("speaker_xml_id") == "11004220"), None
        )
        assert speech is not None
        assert speech.get("party") == "BÜNDNIS 90/DIE GRÜNEN"


# ---------------------------------------------------------------------------
# TestNonMdbSpeaker — speaker with 999... ID
# ---------------------------------------------------------------------------


class TestNonMdbSpeaker:
    """Non-MdB speaker (ID starting with '999') is parseable but flaggable."""

    def test_non_mdb_speaker_present(self, protocol_xml: str) -> None:
        """Speech with 999... speaker ID is present in the parser output."""
        result = parse_speeches_from_xml(protocol_xml)
        speech = next(
            (s for s in result if (s.get("speaker_xml_id") or "").startswith("999")),
            None,
        )
        assert speech is not None, "Non-MdB speech (id starting with 999) not found"

    def test_non_mdb_speaker_id_prefix(self, protocol_xml: str) -> None:
        """Non-MdB speaker_xml_id starts with '999'."""
        result = parse_speeches_from_xml(protocol_xml)
        speech = next(
            (s for s in result if (s.get("speaker_xml_id") or "").startswith("999")),
            None,
        )
        assert speech is not None
        assert speech["speaker_xml_id"].startswith("999")


# ---------------------------------------------------------------------------
# TestAgendaTopIdMapping — multi-TOP / ZP / outside-any-TOP agenda resolution
# (parser-level coverage for the agenda map the speech_key depends on)
# ---------------------------------------------------------------------------

_MULTI_TOP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitzungsverlauf>
  <sitzungstitel>101. Sitzung des Deutschen Bundestages</sitzungstitel>
  <rede id="R-OPEN">
    <p klasse="redner">
      <redner id="11000010">
        <name><vorname>Erste</vorname><nachname>Rednerin</nachname><fraktion>SPD</fraktion></name>
      </redner>Erste Rednerin (SPD):</p>
    <p klasse="J">Eroeffnungsrede ausserhalb jedes Tagesordnungspunkts.</p>
  </rede>
  <tagesordnungspunkt top-id="20">
    <rede id="R-T20">
      <p klasse="redner">
        <redner id="11000011">
          <name><vorname>Zweiter</vorname><nachname>Redner</nachname><fraktion>SPD</fraktion></name>
        </redner>Zweiter Redner (SPD):</p>
      <p klasse="J">Rede unter Tagesordnungspunkt 20.</p>
    </rede>
  </tagesordnungspunkt>
  <tagesordnungspunkt top-id="21">
    <rede id="R-T21">
      <p klasse="redner">
        <redner id="11000012">
          <name><vorname>Dritte</vorname><nachname>Rednerin</nachname><fraktion>FDP</fraktion></name>
        </redner>Dritte Rednerin (FDP):</p>
      <p klasse="J">Rede unter Tagesordnungspunkt 21.</p>
    </rede>
  </tagesordnungspunkt>
  <tagesordnungspunkt top-id="ZP5">
    <rede id="R-ZP5">
      <p klasse="redner">
        <redner id="11000013">
          <name><vorname>Vierter</vorname><nachname>Redner</nachname><fraktion>AfD</fraktion></name>
        </redner>Vierter Redner (AfD):</p>
      <p klasse="J">Rede unter Zusatzpunkt 5.</p>
    </rede>
  </tagesordnungspunkt>
</sitzungsverlauf>
"""


class TestAgendaTopIdMapping:
    """agenda_top_id resolves per enclosing <tagesordnungspunkt>, incl. ZP and none."""

    def test_agenda_top_id_mapping(self) -> None:
        """Multiple TOPs, a Zusatzpunkt, and a rede outside any TOP map correctly."""
        result = parse_speeches_from_xml(_MULTI_TOP_XML)
        agenda_by_rede = {s["xml_rede_id"]: s.get("agenda_top_id") for s in result}
        assert agenda_by_rede == {
            "R-OPEN": None,  # outside any tagesordnungspunkt → no-agenda fallback
            "R-T20": "20",
            "R-T21": "21",
            "R-ZP5": "ZP5",  # Zusatzpunkt keeps its distinct top-id
        }


# ---------------------------------------------------------------------------
# TestDefusedXmlHardening — billion-laughs regression guard
# ---------------------------------------------------------------------------


class TestDefusedXmlHardening:
    """defusedxml blocks entity-expansion / billion-laughs attacks on remote XML."""

    def test_billion_laughs_raises(self) -> None:
        """A billion-laughs payload raises defusedxml.EntitiesForbidden, not OOM."""
        billion_laughs = (
            '<?xml version="1.0"?>'
            "<!DOCTYPE lolz ["
            '  <!ENTITY lol "lol">'
            '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
            '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
            "]>"
            "<root>&lol3;</root>"
        )
        import defusedxml

        with pytest.raises(defusedxml.EntitiesForbidden):
            parse_speeches_from_xml(billion_laughs)


# ---------------------------------------------------------------------------
# TestCitationCoordinates — TOC xref page map + PDF page derivation
# ---------------------------------------------------------------------------


class TestCitationCoordinates:
    """Every rede with a TOC xref carries printed page, quadrant, and PDF page."""

    def test_pages_and_quadrants_mapped(self, protocol_xml: str) -> None:
        result = parse_speeches_from_xml(protocol_xml)
        by_id = {s["xml_rede_id"]: s for s in result}
        assert by_id["ID215000100"]["source_page"] == "12001"
        assert by_id["ID215000100"]["page_quadrant"] == "A"
        assert by_id["ID215000200"]["source_page"] == "12003"
        assert by_id["ID215000200"]["page_quadrant"] == "C"

    def test_pdf_page_derived_from_start_seitennr(self, protocol_xml: str) -> None:
        """pdf_page = printed page − start-seitennr + 1 (root start-seitennr=12000)."""
        result = parse_speeches_from_xml(protocol_xml)
        by_id = {s["xml_rede_id"]: s for s in result}
        assert by_id["ID215000100"]["pdf_page"] == 2
        assert by_id["ID215000300"]["pdf_page"] == 6

    def test_missing_start_seitennr_yields_no_pdf_page(self) -> None:
        """Without start-seitennr the PDF offset is unknowable — pdf_page must
        be None (a deep link must not guess), while the printed page stays."""
        xml = (
            "<dbtplenarprotokoll>"
            "<vorspann><inhaltsverzeichnis>"
            '<ivz-eintrag><xref ref-type="rede" rid="ID1" pnr="500" div="D"/></ivz-eintrag>'
            "</inhaltsverzeichnis></vorspann>"
            '<sitzungsverlauf><rede id="ID1">'
            '<p klasse="redner"><redner id="11001111"><name>'
            "<vorname>Test</vorname><nachname>Person</nachname>"
            "<fraktion>SPD</fraktion></name></redner>Test Person (SPD):</p>"
            '<p klasse="J">Inhalt der Rede.</p>'
            "</rede></sitzungsverlauf></dbtplenarprotokoll>"
        )
        result = parse_speeches_from_xml(xml)
        assert result[0]["source_page"] == "500"
        assert result[0]["pdf_page"] is None
