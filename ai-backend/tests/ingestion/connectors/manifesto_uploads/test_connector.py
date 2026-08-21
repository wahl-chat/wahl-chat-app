# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for ManifestoUploadsConnector — manifest semantics and error handling.

The manifest is the complete statement of what should exist, so the behaviours
under test are: every entry is offered every run, a REMOVED entry is still visited
and retires its stored chunks, and a document that merely fails to read keeps its
existing chunks rather than being silently dropped from the corpus.
"""

from __future__ import annotations

import types
from pathlib import Path
from typing import Optional

import pytest

from src.ingestion.connectors.manifesto_uploads.connector import (
    ManifestoUploadsConnector,
    ManifestUnavailable,
    load_manifest,
)
from src.ingestion.connectors.manifesto_uploads.storage_paths import UploadPathError

_CTX = "landtagswahl-sachsen-anhalt-2026"
_SPD = f"public/{_CTX}/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_CDU = f"public/{_CTX}/wahlprogramme/cdu/Wahlprogramm-CDU_2026-03-24.pdf"


def _manifest(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "dev.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ===========================================================================
# load_manifest
# ===========================================================================


class TestLoadManifest:
    """Comments, blanks and mixed entry forms; a bad line is loud."""

    def test_reads_entries_ignoring_comments_and_blanks(self, tmp_path: Path) -> None:
        path = _manifest(
            tmp_path,
            "# Sachsen-Anhalt",
            "",
            _SPD,
            f"{_CDU}  # draft version",
            "   ",
        )
        assert load_manifest(path) == [_SPD, _CDU]

    def test_deduplicates_while_preserving_order(self, tmp_path: Path) -> None:
        path = _manifest(tmp_path, _CDU, _SPD, _CDU)
        assert load_manifest(path) == [_CDU, _SPD]

    def test_mixed_entry_forms_normalise(self, tmp_path: Path) -> None:
        path = _manifest(
            tmp_path,
            f"https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app/{_SPD}",
            f"firebase/storage_data/{_CDU}",
        )
        assert load_manifest(path) == [_SPD, _CDU]

    def test_malformed_line_raises_with_line_number(self, tmp_path: Path) -> None:
        # Skipping it silently would leave a document un-ingested with no signal.
        path = _manifest(tmp_path, _SPD, "public/e/wahlprogramme/spd/no-date.pdf")
        with pytest.raises(UploadPathError, match="dev.txt:2"):
            load_manifest(path)

    def test_absent_manifest_raises_rather_than_reading_as_empty(
        self, tmp_path: Path
    ) -> None:
        # An empty work-list retires the stored uploads, so a missing file must
        # never produce one — that would let a bad deploy wipe the corpus.
        with pytest.raises(ManifestUnavailable, match="refusing"):
            load_manifest(tmp_path / "missing.txt")

    def test_present_but_empty_manifest_is_a_valid_empty_work_list(
        self, tmp_path: Path
    ) -> None:
        # The deliberate counterpart: the file exists and says "nothing".
        assert load_manifest(_manifest(tmp_path)) == []


# ===========================================================================
# discover — manifest plus store-side retirements
# ===========================================================================


class _FakeQdrant:
    """Serves the connector's stored-object-path scroll and AW-overlap count."""

    def __init__(self, stored_paths: list[str]) -> None:
        self._stored = stored_paths
        self.scroll_filters: list[object] = []

    def count(self, **kwargs):  # noqa: ANN003, ANN201
        """No AW-sourced copy of anything. Must be answered, not left to raise.

        A store that cannot answer the overlap count now fails the item rather than
        assuming "no AW copy" (see OverlapCheckUnavailable), so a fake without this
        method would make every normalize() test fail for the wrong reason.
        """
        return types.SimpleNamespace(count=0)

    def scroll(self, **kwargs):  # noqa: ANN003, ANN201
        self.scroll_filters.append(kwargs.get("scroll_filter"))
        points = [
            type(
                "P",
                (),
                {"payload": {"meta": {"storage_object_path": p}}, "id": str(i)},
            )()
            for i, p in enumerate(self._stored)
        ]
        return points, None


def _connector(manifest: Path, stored: Optional[list[str]] = None):
    connector = ManifestoUploadsConnector(manifest_path=manifest, env="dev")
    if stored is not None:
        connector.bind_store(_FakeQdrant(stored), "test_collection")
    return connector


class TestDiscover:
    """Every manifest entry, plus anything stored that the manifest dropped."""

    def test_returns_manifest_entries_sorted(self, tmp_path: Path) -> None:
        connector = _connector(_manifest(tmp_path, _SPD, _CDU), stored=[])
        assert connector.discover(None) == sorted([_SPD, _CDU])

    def test_ignores_the_cursor(self, tmp_path: Path) -> None:
        connector = _connector(_manifest(tmp_path, _SPD), stored=[])
        assert connector.discover(None) == connector.discover(999999)

    def test_includes_stored_documents_absent_from_the_manifest(
        self, tmp_path: Path
    ) -> None:
        # Removing a line must retire the document, not orphan its chunks forever.
        connector = _connector(_manifest(tmp_path, _SPD), stored=[_SPD, _CDU])
        assert connector.discover(None) == sorted([_SPD, _CDU])

    def test_works_without_a_bound_store(self, tmp_path: Path) -> None:
        connector = _connector(_manifest(tmp_path, _SPD))
        assert connector.discover(None) == [_SPD]

    def test_scroll_is_scoped_to_uploaded_manifestos(self, tmp_path: Path) -> None:
        connector = _connector(_manifest(tmp_path, _SPD), stored=[_SPD])
        connector.discover(None)
        conditions = {
            (c.key, c.match.value)
            for c in getattr(connector._store_client.scroll_filters[0], "must", [])
        }
        assert ("source_type", "party_manifesto") in conditions
        assert ("source", "upload") in conditions


# ===========================================================================
# fetch / normalize
# ===========================================================================


class TestRetirement:
    """A dropped entry normalises to zero chunks, which the runner cleans up."""

    def test_fetch_flags_a_document_missing_from_the_manifest(
        self, tmp_path: Path
    ) -> None:
        connector = _connector(_manifest(tmp_path, _SPD), stored=[_SPD, _CDU])
        connector.discover(None)
        assert connector.fetch(_CDU)["retired"] is True

    def test_normalize_returns_no_chunks_for_a_retired_document(
        self, tmp_path: Path
    ) -> None:
        connector = _connector(_manifest(tmp_path, _SPD), stored=[_SPD, _CDU])
        connector.discover(None)
        assert connector.normalize(connector.fetch(_CDU)) == []


class TestNormalizeErrors:
    """A read/validation failure raises, so the stored copy survives."""

    def test_unreadable_document_raises(self, tmp_path: Path) -> None:
        connector = _connector(_manifest(tmp_path, _SPD), stored=[])
        connector.discover(None)
        raw = connector.fetch(_SPD)  # not staged, and the bucket URL is unreachable
        assert "skip_reason" in raw
        with pytest.raises(ValueError):
            connector.normalize(raw)

    def test_unknown_election_raises(self, tmp_path: Path) -> None:
        bad = (
            "public/landtagswahl-nowhere-2026/wahlprogramme/spd/Programm_2026-01-01.pdf"
        )
        connector = _connector(_manifest(tmp_path, bad), stored=[])
        connector.discover(None)
        with pytest.raises(ValueError, match="unknown election"):
            connector.normalize(
                {"object_path": bad, "pages": [(1, "Text " * 200)], "total_pages": 1}
            )

    def test_party_not_in_election_raises(self, tmp_path: Path) -> None:
        bad = f"public/{_CTX}/wahlprogramme/nichtantretende-partei/Programm_2026-01-01.pdf"
        connector = _connector(_manifest(tmp_path, bad), stored=[])
        connector.discover(None)
        with pytest.raises(ValueError, match="not configured for election"):
            connector.normalize(
                {"object_path": bad, "pages": [(1, "Text " * 200)], "total_pages": 1}
            )

    def test_text_free_pdf_raises_pointing_at_ocr(self, tmp_path: Path) -> None:
        # A scanned PDF parses fine but yields nothing; embedding zero chunks would
        # look like a successful ingest of an empty programme.
        connector = _connector(_manifest(tmp_path, _SPD), stored=[])
        connector.discover(None)
        with pytest.raises(ValueError, match="OCR"):
            connector.normalize(
                {"object_path": _SPD, "pages": [(1, "  "), (2, "")], "total_pages": 2}
            )


def test_normalize_builds_records_from_parsed_pages(tmp_path: Path) -> None:
    connector = _connector(_manifest(tmp_path, _SPD), stored=[])
    connector.discover(None)
    records = connector.normalize(
        {
            "object_path": _SPD,
            "pages": [(1, "Erster Absatz. " * 40), (2, "Zweiter Absatz. " * 40)],
            "total_pages": 2,
        }
    )
    assert records
    assert {r.party_id for r in records} == {"spd"}
    assert {r.region for r in records} == {"DE-ST"}
    assert {r.source for r in records} == {"upload"}
    # Page anchors follow the page each chunk came from.
    assert any(r.citation_url.endswith("#page=1") for r in records)
    assert any(r.citation_url.endswith("#page=2") for r in records)


def test_connector_declares_the_shared_source_type_and_discriminator() -> None:
    connector = ManifestoUploadsConnector()
    assert connector.source_type == "party_manifesto"
    assert connector.source == "upload"
    # Cursor scoping defaults to the connector's own source, keeping the AW
    # manifesto cursor independent of this one.
    assert connector.cursor_source == "upload"
