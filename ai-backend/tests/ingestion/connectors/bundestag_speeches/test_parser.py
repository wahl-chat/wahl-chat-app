# SPDX-FileCopyrightText: 2025 wahl.chat
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
# TestDefusedXmlHardening — billion-laughs regression guard
# ---------------------------------------------------------------------------


class TestDefusedXmlHardening:
    """defusedxml blocks entity-expansion / billion-laughs attacks on remote XML."""

    def test_billion_laughs_raises(self) -> None:
        """A billion-laughs payload raises defusedxml.EntitiesForbidden, not OOM."""
        billion_laughs = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE lolz ['
            '  <!ENTITY lol "lol">'
            '  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">'
            '  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">'
            "]>"
            "<root>&lol3;</root>"
        )
        import defusedxml

        with pytest.raises(defusedxml.EntitiesForbidden):
            parse_speeches_from_xml(billion_laughs)
