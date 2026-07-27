# SPDX-FileCopyrightText: 2026 wahl.chat
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
        # citation_url is the original source (AW file) URL — with a per-chunk
        # #page anchor so the citation opens on the supporting page.
        assert rec.citation_url == "https://example.com/spd-programm-2025.pdf#page=1"

    def test_link_pages_have_no_page_numbers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        # Every candidate failed → the skip reason enumerates the attempts.
        assert "PDF download failed: boom" in raw["skip_reason"]
        assert raw["skip_reason"].startswith("all source candidates failed")
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
        monkeypatch.setattr(connector, "_get_ingested_program_ids", lambda: {598})

        # Under the OLD watermark filter, since=598 would exclude 555 forever.
        ids = connector.discover(since=598)

        assert "555" in ids, "a failed-below-max program must be re-discovered"
        assert "598" not in ids, "already-ingested programs must be excluded"

    def test_no_floor_by_default_includes_old_program(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With MANIFESTO_SINCE unset there is NO built-in cut-off — an old
        program (would-be-excluded under the former hardcoded 2020 floor) is
        ingested."""
        monkeypatch.delenv("MANIFESTO_SINCE", raising=False)
        old_program = dict(_PDF_PROGRAM, id=100)

        connector = ManifestoConnector()
        connector._client = self._FakeAwClient([old_program])  # type: ignore[assignment]
        monkeypatch.setattr(
            conn_mod, "_fetch_period_date", lambda *a, **k: "2017-09-24"
        )
        monkeypatch.setattr(connector, "_get_ingested_program_ids", lambda: set())

        assert connector.discover(since=None) == ["100"]

    def test_manifesto_since_floors_out_older_programs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MANIFESTO_SINCE excludes programs whose election_date is before it,
        and keeps those on or after it."""
        # Distinct parliament_period ids so each maps to its own election_date.
        old_program = dict(
            _PDF_PROGRAM, id=100, parliament_period={"id": 900, "label": "old"}
        )
        new_program = dict(
            _PDF_PROGRAM, id=101, parliament_period={"id": 901, "label": "new"}
        )
        dates = {900: "2017-09-24", 901: "2025-02-23"}

        connector = ManifestoConnector()
        connector._client = self._FakeAwClient([old_program, new_program])  # type: ignore[assignment]
        monkeypatch.setattr(
            conn_mod,
            "_fetch_period_date",
            lambda _client, period_id, _cache: dates[period_id],
        )
        monkeypatch.setattr(connector, "_get_ingested_program_ids", lambda: set())
        monkeypatch.setenv("MANIFESTO_SINCE", "2020-01-01")

        ids = connector.discover(since=None)
        assert ids == ["101"], f"only the >= floor program is kept, got {ids!r}"

    def test_invalid_manifesto_since_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A malformed MANIFESTO_SINCE surfaces loudly rather than silently
        ingesting everything."""
        monkeypatch.setenv("MANIFESTO_SINCE", "not-a-date")
        with pytest.raises(ValueError, match="MANIFESTO_SINCE must be an ISO date"):
            conn_mod.resolve_since_floor()


class TestManifestoRefresh:
    """MANIFESTO_REFRESH=1 skips the ingested-ids exclusion so run.py's
    content-hash rewrite + orphan cleanup can reconcile replaced PDFs."""

    def test_refresh_includes_already_ingested_programs(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ingested_program = dict(_PDF_PROGRAM, id=598)
        new_program = dict(_PDF_PROGRAM, id=700)

        connector = ManifestoConnector()
        connector._client = TestDiscoverSetDifference._FakeAwClient(  # type: ignore[assignment]
            [ingested_program, new_program]
        )
        monkeypatch.setattr(
            conn_mod, "_fetch_period_date", lambda *a, **k: "2025-02-23"
        )

        def _boom() -> set[int]:
            raise AssertionError(
                "MANIFESTO_REFRESH must not touch Qdrant for the ingested-ids set"
            )

        monkeypatch.setattr(connector, "_get_ingested_program_ids", _boom)
        monkeypatch.setenv("MANIFESTO_REFRESH", "1")

        ids = connector.discover(since=None)

        assert ids == ["598", "700"], (
            "refresh discover must return ALL eligible programs (incl. ingested), "
            f"got {ids!r}"
        )

    def test_refresh_flag_parsing_matches_aw_refresh(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """'true'/'yes'/'1' enable refresh; other values do not."""
        ingested_program = dict(_PDF_PROGRAM, id=598)

        for value, expect_included in [
            ("true", True),
            ("YES", True),
            ("1", True),
            ("0", False),
            ("off", False),
            ("", False),
        ]:
            connector = ManifestoConnector()
            connector._client = TestDiscoverSetDifference._FakeAwClient(  # type: ignore[assignment]
                [ingested_program]
            )
            monkeypatch.setattr(
                conn_mod, "_fetch_period_date", lambda *a, **k: "2025-02-23"
            )
            monkeypatch.setattr(connector, "_get_ingested_program_ids", lambda: {598})
            monkeypatch.setenv("MANIFESTO_REFRESH", value)

            ids = connector.discover(since=None)
            assert ("598" in ids) is expect_included, (
                f"MANIFESTO_REFRESH={value!r}: expected included={expect_included}, got {ids!r}"
            )


class TestDetermineSource:
    """determine_source precedence — link[0].uri wins over file; both
    null raises; a non-dict link entry falls back to file."""

    def test_link_uri_wins_over_file(self) -> None:
        program = {
            "link": [{"uri": "https://example.com/programm", "title": "Programm"}],
            "file": "https://example.com/programm.pdf",
        }
        assert conn_mod.determine_source(program) == (
            "link",
            "https://example.com/programm",
        )

    def test_file_used_when_no_link(self) -> None:
        program = {"link": [], "file": "https://example.com/programm.pdf"}
        assert conn_mod.determine_source(program) == (
            "pdf",
            "https://example.com/programm.pdf",
        )

    def test_null_link_uri_falls_back_to_file(self) -> None:
        program = {
            "link": [{"uri": None, "title": "kaputt"}],
            "file": "https://example.com/programm.pdf",
        }
        assert conn_mod.determine_source(program) == (
            "pdf",
            "https://example.com/programm.pdf",
        )

    def test_non_dict_link_entry_falls_back_to_file(self) -> None:
        program = {
            "link": ["https://not-a-dict.example.com"],
            "file": "https://example.com/programm.pdf",
        }
        assert conn_mod.determine_source(program) == (
            "pdf",
            "https://example.com/programm.pdf",
        )

    def test_both_null_raises(self) -> None:
        with pytest.raises(ValueError, match="no link or file"):
            conn_mod.determine_source({"link": [], "file": None})


class TestLoadProgramPagesHtmlFloor:
    """HTML sources shorter than 500 extracted chars are skipped (a
    'download our program' landing page must not be embedded)."""

    class _FakeResponse:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    def test_short_html_raises_floor_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        nav_only = "<html><body><nav><a href='/'>Home</a></nav></body></html>"
        monkeypatch.setattr(
            "requests.get", lambda *a, **k: self._FakeResponse(nav_only)
        )
        with pytest.raises(ValueError, match="HTML too short"):
            conn_mod.load_program_pages("link", "https://example.com/landing")

    def test_long_html_passes_floor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        paragraph = (
            "<p>"
            + ("Wir fordern bezahlbaren Wohnraum für alle Menschen. " * 20)
            + "</p>"
        )
        html = (
            f"<html><body><article><h1>Programm</h1>{paragraph}</article></body></html>"
        )
        monkeypatch.setattr("requests.get", lambda *a, **k: self._FakeResponse(html))
        result = conn_mod.load_program_pages("link", "https://example.com/programm")
        assert result["total_pages"] is None
        assert len(result["pages"]) == 1
        page_no, text = result["pages"][0]
        assert page_no == 1
        assert len(text) >= 500


class TestGetIngestedProgramIds:
    """_get_ingested_program_ids paginates the Qdrant scroll and filters
    non-int external_ids."""

    class _Point:
        def __init__(self, payload: dict | None) -> None:
            self.payload = payload

    class _PagingQdrant:
        """Two scroll pages; second page carries the terminating None offset."""

        def __init__(self) -> None:
            self.calls: list[object] = []

        def scroll(self, **kwargs: object) -> tuple:
            offset = kwargs.get("offset")
            self.calls.append(offset)
            P = TestGetIngestedProgramIds._Point
            if offset is None:
                return (
                    [P({"external_id": 598}), P({"external_id": "not-int"})],
                    "page-2-offset",
                )
            return (
                [P({"external_id": 700}), P(None), P({"external_id": 3.5})],
                None,
            )

    def test_pagination_and_non_int_filtering(self) -> None:
        connector = ManifestoConnector()
        fake = self._PagingQdrant()
        connector._qdrant = fake  # type: ignore[assignment]

        ids = connector._get_ingested_program_ids()

        assert ids == {598, 700}, f"expected int-only ids across pages, got {ids!r}"
        assert fake.calls == [None, "page-2-offset"], (
            "scroll must be called once per page, chaining next_offset"
        )


class TestSourceFallback:
    """A dead preferred HTML link falls back to the PDF instead of skipping."""

    def test_html_failure_falls_back_to_pdf(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        program = {
            "id": 129,
            "label": "Programm",
            "party": {"label": "SPD"},
            "parliament_period": {"id": 50, "label": "Bundestag Wahl 2021"},
            "link": [{"uri": "https://archive.example/dead-viewer"}],
            "file": "https://example.com/program-129.pdf",
        }
        connector = ManifestoConnector()
        _seed(connector, program, "2021-09-26")

        def _fake_load(source_kind: object, source_url: str) -> dict:
            if "dead-viewer" in source_url:
                raise ValueError("HTML fetch failed: 404")
            return {"pages": [(1, "PDF Inhalt " * 100)], "total_pages": 1}

        monkeypatch.setattr(conn_mod, "load_program_pages", _fake_load)

        raw = connector.fetch("129")
        assert "skip_reason" not in raw, (
            f"PDF fallback must rescue the program, got skip: {raw.get('skip_reason')}"
        )
        assert raw["source_url"] == "https://example.com/program-129.pdf"
        records = connector.normalize(raw)
        assert records, "the fallback-fetched program must normalize to chunks"


class TestCompletenessAwareSetDifference:
    """One stored chunk is NOT proof a program committed completely."""

    class _Store:
        """Fake store: program 600 has 2 of 3 chunks stored (partial commit),
        program 700 has 2 of 2 (complete)."""

        def scroll(self, **kwargs: object) -> tuple:
            from types import SimpleNamespace

            points = [
                SimpleNamespace(
                    id=f"p600-{i}",
                    payload={
                        "external_id": 600,
                        "meta": {"total_chunks": 3},
                    },
                )
                for i in range(2)
            ] + [
                SimpleNamespace(
                    id=f"p700-{i}",
                    payload={
                        "external_id": 700,
                        "meta": {"total_chunks": 2},
                    },
                )
                for i in range(2)
            ]
            return (points, None)

    def test_partial_program_is_rediscovered(self) -> None:
        connector = ManifestoConnector()
        connector.bind_store(self._Store(), "wahlchat_chunks_test")
        ingested = connector._get_ingested_program_ids()
        assert 700 in ingested, "a complete program counts as ingested"
        assert 600 not in ingested, (
            "a partially-committed program (2/3 chunks) must be re-discovered "
            "so the runner's footprint comparison repairs the missing tail"
        )
