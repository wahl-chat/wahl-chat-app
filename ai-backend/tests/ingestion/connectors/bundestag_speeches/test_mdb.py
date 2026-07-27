# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for bundestag_speeches.mdb:
  - load_mdb_lookup: parses the tiny MdB-Stammdaten XML into {by_id, by_name} dicts
  - ensure_mdb_lookup: live-run loader — fetches on miss, fails loud on empty
  - download_mdb_stammdaten: extracts the OpenData ZIP; 404 fails fast
  - mdb_party_for_speech: resolves party by speaker_xml_id, fallback by name
  - mdb_record_for_speaker_name: looks up MdB record by normalized name
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from src.ingestion.connectors.bundestag_speeches import mdb as mdb_module
from src.ingestion.connectors.bundestag_speeches.mdb import (
    StammdatenUnavailableError,
    download_mdb_stammdaten,
    ensure_mdb_lookup,
    load_mdb_lookup,
    mdb_party_for_speech,
    mdb_record_for_speaker_name,
)


class _FakeResponse:
    """Minimal httpx.Response stand-in for the download path."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content

    def raise_for_status(self) -> None:
        # 5xx would raise here in real httpx; the tests only drive 200 / 404.
        return None


# ---------------------------------------------------------------------------
# TestLoadMdbLookup — fixture parsing
# ---------------------------------------------------------------------------


class TestLoadMdbLookup:
    """load_mdb_lookup parses the MdB-Stammdaten XML into lookup dicts."""

    def test_returns_dict_with_keys(self, mdb_xml_path: Path) -> None:
        """load_mdb_lookup returns a dict with 'by_id' and 'by_name' keys."""
        result = load_mdb_lookup(mdb_xml_path)
        assert isinstance(result, dict)
        assert "by_id" in result
        assert "by_name" in result

    def test_by_id_contains_scholz(self, mdb_xml_path: Path) -> None:
        """by_id lookup contains Scholz (ID 11004870)."""
        result = load_mdb_lookup(mdb_xml_path)
        assert "11004870" in result["by_id"], "Scholz MdB record not found by ID"

    def test_by_id_contains_baerbock(self, mdb_xml_path: Path) -> None:
        """by_id lookup contains Baerbock (ID 11004220)."""
        result = load_mdb_lookup(mdb_xml_path)
        assert "11004220" in result["by_id"], "Baerbock MdB record not found by ID"

    def test_scholz_party_spd(self, mdb_xml_path: Path) -> None:
        """Scholz party resolves to 'SPD' via PARTEI_KURZ."""
        result = load_mdb_lookup(mdb_xml_path)
        record = result["by_id"]["11004870"]
        assert record["party"] == "SPD"

    def test_baerbock_party_gruene(self, mdb_xml_path: Path) -> None:
        """Baerbock party resolves to 'BÜNDNIS 90/DIE GRÜNEN' via PARTEI_KURZ."""
        result = load_mdb_lookup(mdb_xml_path)
        record = result["by_id"]["11004220"]
        assert record["party"] == "BÜNDNIS 90/DIE GRÜNEN"

    def test_merz_party_via_wahlperioden(self, mdb_xml_path: Path) -> None:
        """Merz (ID 11003444): PARTEI_KURZ empty → party resolved via WAHLPERIODEN Fraktion/Gruppe."""
        result = load_mdb_lookup(mdb_xml_path)
        assert "11003444" in result["by_id"], "Merz MdB record not found by ID"
        record = result["by_id"]["11003444"]
        # Party must be resolved from WAHLPERIODE WP=21 INSTITUTION INS_LANG=CDU/CSU
        assert record["party"] is not None, (
            "Party must resolve via WAHLPERIODEN fallback"
        )
        assert "CDU" in record["party"] or record["party"] == "CDU/CSU"

    def test_missing_file_returns_empty_lookups(self, tmp_path: Path) -> None:
        """load_mdb_lookup returns empty lookups (not an error) when the file is absent."""
        missing = tmp_path / "nonexistent.xml"
        result = load_mdb_lookup(missing)
        assert result == {"by_id": {}, "by_name": {}}, (
            "Missing MdB file must return empty lookups, not raise"
        )

    def test_by_name_lookup_populated(self, mdb_xml_path: Path) -> None:
        """by_name lookup contains at least one entry (unambiguous name→record mapping)."""
        result = load_mdb_lookup(mdb_xml_path)
        assert len(result["by_name"]) >= 1, "by_name must contain at least one entry"


# ---------------------------------------------------------------------------
# TestMdbPartyForSpeech — party resolution by id + name fallback
# ---------------------------------------------------------------------------


class TestMdbPartyForSpeech:
    """mdb_party_for_speech resolves party from lookup by id, then by normalized name."""

    def test_party_by_id(self, mdb_xml_path: Path) -> None:
        """Resolves party 'SPD' for Scholz by speaker_xml_id."""
        lookup = load_mdb_lookup(mdb_xml_path)
        speech = {"speaker_xml_id": "11004870", "speaker_name": "Olaf Scholz"}
        assert mdb_party_for_speech(speech, lookup) == "SPD"

    def test_party_by_name_fallback(self, mdb_xml_path: Path) -> None:
        """Resolves party by normalized name when speaker_xml_id is not in lookup."""
        lookup = load_mdb_lookup(mdb_xml_path)
        # Use an id that is NOT in the fixture, but use the real name
        speech = {"speaker_xml_id": "UNKNOWN_ID", "speaker_name": "Annalena Baerbock"}
        result = mdb_party_for_speech(speech, lookup)
        # Party should resolve via by_name lookup
        assert result == "BÜNDNIS 90/DIE GRÜNEN"

    def test_unknown_speaker_returns_none(self, mdb_xml_path: Path) -> None:
        """Returns None for a speaker not in the lookup (neither by id nor name)."""
        lookup = load_mdb_lookup(mdb_xml_path)
        speech = {"speaker_xml_id": "UNKNOWN", "speaker_name": "Unknown Person"}
        assert mdb_party_for_speech(speech, lookup) is None

    def test_empty_lookup_returns_none(self) -> None:
        """Returns None for any speaker when lookup is empty."""
        empty_lookup: dict = {"by_id": {}, "by_name": {}}
        speech = {"speaker_xml_id": "11004870", "speaker_name": "Olaf Scholz"}
        assert mdb_party_for_speech(speech, empty_lookup) is None


# ---------------------------------------------------------------------------
# TestMdbRecordForSpeakerName — record lookup by normalized name
# ---------------------------------------------------------------------------


class TestMdbRecordForSpeakerName:
    """mdb_record_for_speaker_name looks up MdB record by normalized speaker name."""

    def test_known_name_returns_record(self, mdb_xml_path: Path) -> None:
        """Returns an MdB record dict for a known speaker name."""
        lookup = load_mdb_lookup(mdb_xml_path)
        speech = {"speaker_name": "Olaf Scholz"}
        record = mdb_record_for_speaker_name(speech, lookup)
        assert record is not None
        assert isinstance(record, dict)
        assert "id" in record

    def test_unknown_name_returns_none(self, mdb_xml_path: Path) -> None:
        """Returns None for an unknown speaker name."""
        lookup = load_mdb_lookup(mdb_xml_path)
        speech = {"speaker_name": "Unknown Speaker"}
        assert mdb_record_for_speaker_name(speech, lookup) is None

    def test_empty_name_returns_none(self, mdb_xml_path: Path) -> None:
        """Returns None for an empty speaker name."""
        lookup = load_mdb_lookup(mdb_xml_path)
        speech = {"speaker_name": ""}
        assert mdb_record_for_speaker_name(speech, lookup) is None


# ---------------------------------------------------------------------------
# TestEnsureMdbLookup — live-run loader (fail-loud on empty, no silent degrade)
# ---------------------------------------------------------------------------


class TestEnsureMdbLookup:
    """ensure_mdb_lookup requires a non-empty lookup for the live speech path."""

    def test_present_file_returns_lookup(self, mdb_xml_path: Path) -> None:
        """A present, non-empty file loads without a download attempt."""
        result = ensure_mdb_lookup(mdb_xml_path, download=False)
        assert result["by_id"], "expected a populated lookup from the fixture"

    def test_missing_file_no_download_raises(self, tmp_path: Path) -> None:
        """Absent file with download disabled fails loud rather than degrading."""
        with pytest.raises(StammdatenUnavailableError):
            ensure_mdb_lookup(tmp_path / "nonexistent.xml", download=False)


# ---------------------------------------------------------------------------
# TestDownloadMdbStammdaten — ZIP extraction + fail-fast on a rotated blob
# ---------------------------------------------------------------------------


class TestDownloadMdbStammdaten:
    """download_mdb_stammdaten extracts the OpenData ZIP; a 404 fails fast."""

    def test_extracts_xml_member(
        self, mdb_xml_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 200 ZIP response is extracted to dest and is loadable."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.write(mdb_xml_path, arcname="MDB_STAMMDATEN.XML")

        monkeypatch.setattr(
            mdb_module.httpx, "get", lambda *a, **k: _FakeResponse(200, buf.getvalue())
        )
        dest = tmp_path / "MDB_STAMMDATEN.XML"
        download_mdb_stammdaten(dest)
        assert dest.exists()
        assert load_mdb_lookup(dest)["by_id"], "extracted file must be loadable"

    def test_404_raises_without_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 404 (rotated blob) is non-retryable and fails loud immediately."""
        calls = {"n": 0}

        def _get(*_a, **_k) -> _FakeResponse:
            calls["n"] += 1
            return _FakeResponse(404)

        monkeypatch.setattr(mdb_module.httpx, "get", _get)
        with pytest.raises(StammdatenUnavailableError):
            download_mdb_stammdaten(tmp_path / "out.xml")
        assert calls["n"] == 1, "404 must not be retried"
