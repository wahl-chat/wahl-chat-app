# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for ManifestoConnector (src/ingestion/connectors/manifestos/connector.py).

Pure: no network, no OpenAI, no Qdrant, no Firestore. The AWClient is never
exercised — discover()'s caches are seeded directly and load_program_pages is
monkeypatched, so fetch()/normalize() are tested without I/O.
"""

from __future__ import annotations

import pytest

from src.ingestion.connector import BaseConnector
from src.ingestion.connectors.manifestos import connector as conn_mod
from src.ingestion.connectors.manifestos.connector import ManifestoConnector
from src.ingestion.schemas import SourceType

_PDF_PROGRAM = {
    "id": 598,
    "label": "Wahlprogramm SPD 2025",
    "party": {"id": 1, "label": "SPD"},
    "parliament_period": {"id": 111, "label": "Bundestag Wahl 2025"},
    "link": [],
    "file": "https://example.com/spd-programm-2025.pdf",
}

_LINK_PROGRAM = {
    "id": 701,
    "label": "Wahlprogramm Grüne Berlin 2023",
    "party": {"id": 5, "label": "BÜNDNIS 90/DIE GRÜNEN"},
    "parliament_period": {"id": 200, "label": "Berlin Wahl 2023"},
    "link": [{"uri": "https://gruene-berlin.de/programm", "title": "Programm"}],
    "file": None,
}


def _seed(connector: ManifestoConnector, program: dict, date_iso: str) -> None:
    """Seed the per-run discover() caches so fetch() can run without discovery."""
    pid = program["id"]
    connector._programs = {pid: program}
    connector._period_dates = {pid: date_iso}


class TestInterface:
    def test_is_base_connector(self) -> None:
        assert issubclass(ManifestoConnector, BaseConnector)

    def test_source_type_is_party_manifesto(self) -> None:
        assert ManifestoConnector.source_type == SourceType.PARTY_MANIFESTO.value


class TestFetchNormalize:
    def test_pdf_fetch_then_normalize(self, monkeypatch: pytest.MonkeyPatch) -> None:
        connector = ManifestoConnector()
        _seed(connector, _PDF_PROGRAM, "2025-02-23")

        monkeypatch.setattr(
            conn_mod,
            "load_program_pages",
            lambda *a, **k: {
                "pages": [(1, "Ein Programmtext. " * 50)],
                "total_pages": 1,
            },
        )

        raw = connector.fetch("598")
        assert raw["source_kind"] == "pdf"
        assert "skip_reason" not in raw

        records = connector.normalize(raw)
        assert records
        rec = records[0]
        assert rec.party_id == "spd"
        assert rec.source_type == SourceType.PARTY_MANIFESTO
        assert rec.external_id == 598
        # citation_url is the original source (AW file) URL, not a re-serve route.
        assert rec.citation_url == "https://example.com/spd-programm-2025.pdf"

    def test_link_pages_have_no_page_numbers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        connector = ManifestoConnector()
        _seed(connector, _LINK_PROGRAM, "2023-09-10")

        monkeypatch.setattr(
            conn_mod,
            "load_program_pages",
            lambda *a, **k: {
                "pages": [(1, "HTML Programmtext. " * 50)],
                "total_pages": None,
            },
        )

        records = connector.normalize(connector.fetch("701"))
        meta = records[0].meta
        assert meta is not None
        assert "page_start" not in meta
        assert "page_end" not in meta
        assert records[0].region == "DE-BE"

    def test_fetch_skip_reason_propagates_as_valueerror(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        connector = ManifestoConnector()
        _seed(connector, _PDF_PROGRAM, "2025-02-23")

        def _boom(*a: object, **k: object) -> dict:
            raise ValueError("PDF download failed: boom")

        monkeypatch.setattr(conn_mod, "load_program_pages", _boom)

        raw = connector.fetch("598")
        assert raw["skip_reason"] == "PDF download failed: boom"
        with pytest.raises(ValueError, match="PDF download failed"):
            connector.normalize(raw)

    def test_program_not_in_cache_skips(self) -> None:
        connector = ManifestoConnector()
        raw = connector.fetch("999")  # nothing seeded
        assert "not in discover cache" in raw["skip_reason"]
        with pytest.raises(ValueError):
            connector.normalize(raw)


class TestDiscoverSetDifference:
    """(a) discover() uses gap-free set-difference against Qdrant, not a
    max-external_id watermark that permanently drops failed-below-max programs."""

    class _FakeAwClient:
        def __init__(self, programs: list[dict]) -> None:
            self._programs = programs

        def get_all(self, endpoint: str, params: dict) -> list[dict]:
            return self._programs

    def test_failed_program_below_max_is_rediscovered(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A program with an id BELOW the stored max (e.g. it transiently failed
        on run 1 while a higher id succeeded) must be re-discovered on run 2;
        already-ingested programs are excluded."""
        failed_program = dict(_PDF_PROGRAM, id=555)
        ingested_program = dict(_PDF_PROGRAM, id=598)

        connector = ManifestoConnector()
        connector._client = self._FakeAwClient([failed_program, ingested_program])  # type: ignore[assignment]
        monkeypatch.setattr(
            conn_mod, "_fetch_period_date", lambda *a, **k: "2025-02-23"
        )
        monkeypatch.setattr(
            connector, "_get_ingested_program_ids", lambda: {598}
        )

        # Under the OLD watermark filter, since=598 would exclude 555 forever.
        ids = connector.discover(since=598)

        assert "555" in ids, "a failed-below-max program must be re-discovered"
        assert "598" not in ids, "already-ingested programs must be excluded"

    def test_cutoff_date_filter_kept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The 2020 _CUTOFF election-date filter still applies with set-difference."""
        old_program = dict(_PDF_PROGRAM, id=100)

        connector = ManifestoConnector()
        connector._client = self._FakeAwClient([old_program])  # type: ignore[assignment]
        monkeypatch.setattr(
            conn_mod, "_fetch_period_date", lambda *a, **k: "2017-09-24"
        )
        monkeypatch.setattr(connector, "_get_ingested_program_ids", lambda: set())

        assert connector.discover(since=None) == []
