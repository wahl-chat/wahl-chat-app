# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for storage_paths.py — the upload path IS the metadata.

Pure (no network, no filesystem writes). Covers:
  (a) parse_object_path   — segments, document date, malformed paths
  (b) to_object_path      — URL / gs:// / staging path / bare path all normalise
  (c) storage_url         — per-env bucket, percent-encoding
  (d) UploadRef.title     — citation-ready document name
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ingestion.connectors.manifesto_uploads.storage_paths import (
    UploadPathError,
    bucket_for_env,
    parse_object_path,
    parse_upload,
    staging_path,
    storage_url,
    to_object_path,
)

_ST = "public/landtagswahl-sachsen-anhalt-2026/spd/Wahlprogramm-SPD-Sachsen-Anhalt-2026_2026-06-01.pdf"


# ===========================================================================
# (a) parse_object_path
# ===========================================================================


class TestParseObjectPath:
    """The path yields election, party, document name and document date."""

    def test_parses_all_segments(self) -> None:
        ref = parse_object_path(_ST)
        assert ref.context_id == "landtagswahl-sachsen-anhalt-2026"
        assert ref.party_id == "spd"
        assert ref.document_name == "Wahlprogramm-SPD-Sachsen-Anhalt-2026"
        assert ref.document_date == date(2026, 6, 1)
        assert ref.object_path == _ST

    def test_title_is_human_readable(self) -> None:
        assert parse_object_path(_ST).title == "Wahlprogramm SPD Sachsen Anhalt 2026"

    def test_document_name_may_contain_dots_and_digits(self) -> None:
        ref = parse_object_path("public/e/spd/Programm-Rev.1.0-2026_2026-03-05.pdf")
        assert ref.document_name == "Programm-Rev.1.0-2026"
        assert ref.document_date == date(2026, 3, 5)

    @pytest.mark.parametrize(
        "bad, why",
        [
            ("public/e/spd/no-date.pdf", "missing date suffix"),
            ("public/e/spd/doc_2026-6-1.pdf", "date not zero-padded ISO"),
            ("public/e/doc_2026-06-01.pdf", "missing party segment"),
            ("private/e/spd/doc_2026-06-01.pdf", "not under public/"),
            ("public/e/spd/doc_2026-06-01.txt", "not a pdf"),
            ("public/e/spd/doc_2026-06-01.pdf/x", "trailing segment"),
        ],
    )
    def test_rejects_malformed_paths(self, bad: str, why: str) -> None:
        with pytest.raises(UploadPathError):
            parse_object_path(bad)

    def test_rejects_impossible_calendar_date(self) -> None:
        # Shape-valid but not a real date. Rejected rather than coerced, because
        # this date is shown to users on the source card.
        with pytest.raises(UploadPathError, match="invalid date"):
            parse_object_path("public/e/spd/doc_2026-02-30.pdf")


# ===========================================================================
# (b) to_object_path — one manifest line survives the move to the bucket
# ===========================================================================


class TestToObjectPath:
    """A manifest entry may be written in any of the four equivalent forms."""

    @pytest.mark.parametrize(
        "entry",
        [
            _ST,
            f"https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app/{_ST}",
            f"https://storage.googleapis.com/wahl-chat.firebasestorage.app/{_ST}",
            f"gs://wahl-chat-dev.firebasestorage.app/{_ST}",
            f"firebase/storage_data/{_ST}",
            f"  {_ST}  ",
        ],
    )
    def test_normalises_to_the_same_object_path(self, entry: str) -> None:
        assert to_object_path(entry) == _ST

    def test_percent_encoded_url_is_decoded(self) -> None:
        encoded = (
            "https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app/"
            "public/e/spd/Programm%20A_2026-06-01.pdf"
        )
        assert to_object_path(encoded) == "public/e/spd/Programm A_2026-06-01.pdf"

    def test_windows_separators_normalise(self) -> None:
        assert to_object_path(_ST.replace("/", "\\")) == _ST

    @pytest.mark.parametrize("bad", ["", "   ", "https://example.com/foo.pdf"])
    def test_rejects_entries_without_a_public_component(self, bad: str) -> None:
        with pytest.raises(UploadPathError):
            to_object_path(bad)

    def test_parse_upload_combines_both_steps(self) -> None:
        ref = parse_upload(f"firebase/storage_data/{_ST}")
        assert (ref.context_id, ref.party_id) == (
            "landtagswahl-sachsen-anhalt-2026",
            "spd",
        )


# ===========================================================================
# (c) storage_url — the citation target
# ===========================================================================


class TestStorageUrl:
    """Citations point at the bucket copy of the exact file we parsed."""

    def test_dev_and_prod_buckets_differ(self) -> None:
        assert bucket_for_env("dev") == "wahl-chat-dev.firebasestorage.app"
        assert bucket_for_env("prod") == "wahl-chat.firebasestorage.app"

    def test_url_shape(self) -> None:
        assert storage_url(_ST, "prod") == (
            "https://storage.googleapis.com/wahl-chat.firebasestorage.app/" + _ST
        )

    def test_slashes_survive_but_spaces_are_encoded(self) -> None:
        url = storage_url("public/e/spd/Programm A_2026-06-01.pdf", "dev")
        assert url.endswith("/public/e/spd/Programm%20A_2026-06-01.pdf")

    def test_unknown_env_is_rejected(self) -> None:
        with pytest.raises(UploadPathError, match="no Storage bucket"):
            bucket_for_env("staging")

    def test_ref_citation_url_matches_storage_url(self) -> None:
        ref = parse_object_path(_ST)
        assert ref.citation_url("dev") == storage_url(_ST, "dev")


def test_staging_path_points_into_firebase_storage_data() -> None:
    path = staging_path(_ST)
    assert path.parts[-5:] == (
        "storage_data",
        "public",
        "landtagswahl-sachsen-anhalt-2026",
        "spd",
        "Wahlprogramm-SPD-Sachsen-Anhalt-2026_2026-06-01.pdf",
    )
    assert path.is_absolute()
