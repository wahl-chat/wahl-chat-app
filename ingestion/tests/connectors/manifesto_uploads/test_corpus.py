# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for the uploaded-manifesto record builder (pure, no I/O).

Covers the envelope fields retrieval depends on (party tenant, region, publish
date, source discriminator), the ``#page=`` citation anchors, the content hash's
sensitivity to provenance-only changes, and the id-space separation from
AW-sourced manifestos.
"""

from __future__ import annotations

from datetime import date

import pytest

from ingestion.connectors.manifesto_uploads.election_fixtures import (
    ElectionFixture,
    FixtureLookupError,
)
from ingestion.connectors.manifesto_uploads.mappers.corpus import (
    UPLOAD_SOURCE,
    build_upload_manifesto_records,
)
from ingestion.connectors.manifesto_uploads.storage_paths import parse_object_path
from ingestion.ids import compute_source_item_id
from ingestion.schemas import AuthorityTier, SourceType

_PATH = "public/landtagswahl-sachsen-anhalt-2026/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
_URL = (
    "https://storage.googleapis.com/wahl-chat-dev.firebasestorage.app/"
    "public/landtagswahl-sachsen-anhalt-2026/wahlprogramme/spd/Wahlprogramm-SPD_2026-06-01.pdf"
)

FIXTURE = ElectionFixture(
    context_id="landtagswahl-sachsen-anhalt-2026",
    name="Landtagswahl Sachsen-Anhalt 2026",
    region="DE-ST",
    level="state",
    election_date=date(2026, 9, 6),
    party_ids=frozenset({"spd", "cdu"}),
)

CHUNKS = [("Erster Absatz.", 1, 1), ("Zweiter Absatz.", 4, 4)]


def _build(chunks=None, fixture=FIXTURE, path=_PATH, url=_URL, total_pages=37):
    return build_upload_manifesto_records(
        ref=parse_object_path(path),
        fixture=fixture,
        chunks=chunks if chunks is not None else CHUNKS,
        citation_url=url,
        total_pages=total_pages,
    )


# ===========================================================================
# Envelope
# ===========================================================================


class TestEnvelope:
    """The indexed fields every filtered query depends on."""

    def test_one_record_per_chunk_with_sequential_indexes(self) -> None:
        records = _build()
        assert [r.chunk_index for r in records] == [0, 1]
        assert [r.text for r in records] == ["Erster Absatz.", "Zweiter Absatz."]

    def test_party_and_region_come_from_path_and_fixture(self) -> None:
        record = _build()[0]
        assert record.party_id == "spd"
        # The election's most specific region — what manifesto retrieval filters on.
        assert record.region == "DE-ST"

    def test_publish_date_is_the_election_date_not_the_document_date(self) -> None:
        # Both manifesto halves stamp the election date so they share one retrieval
        # window; the document's own date is preserved in meta.
        record = _build()[0]
        assert record.publish_date == date(2026, 9, 6)
        assert record.meta["document_date"] == "2026-06-01"

    def test_source_type_tier_and_discriminator(self) -> None:
        record = _build()[0]
        assert record.source_type == SourceType.PARTY_MANIFESTO
        assert record.authority_tier == AuthorityTier.SELF_REPORTED
        assert record.source == UPLOAD_SOURCE

    def test_no_external_id_is_invented(self) -> None:
        # There is no monotonic upstream id for a file; discovery enumerates the
        # manifest instead of walking a cursor.
        assert _build()[0].external_id is None

    def test_chunk_key_matches_source_item_id(self) -> None:
        record = _build()[0]
        assert record.chunk_key == f"{record.source_item_id}:0000"


# ===========================================================================
# Citations
# ===========================================================================


class TestCitations:
    """Anchors are exact because we parsed the file the URL points at."""

    def test_page_anchor_per_chunk(self) -> None:
        records = _build()
        assert records[0].citation_url == f"{_URL}#page=1"
        assert records[1].citation_url == f"{_URL}#page=4"

    def test_existing_fragment_is_never_clobbered(self) -> None:
        record = _build(url=f"{_URL}#page=99")[0]
        assert record.citation_url == f"{_URL}#page=99"

    def test_chunk_without_a_page_keeps_the_plain_url(self) -> None:
        record = _build(chunks=[("Text.", None, None)])[0]
        assert record.citation_url == _URL

    def test_title_names_document_and_election(self) -> None:
        assert (
            _build()[0].citation_title
            == "Wahlprogramm SPD – Landtagswahl Sachsen-Anhalt 2026"
        )


# ===========================================================================
# meta
# ===========================================================================


class TestMeta:
    """Descriptive provenance, including the completed-parent marker."""

    def test_meta_contents(self) -> None:
        meta = _build()[0].meta
        assert meta["context_id"] == "landtagswahl-sachsen-anhalt-2026"
        assert meta["storage_object_path"] == _PATH
        assert meta["document_name"] == "Wahlprogramm-SPD"
        assert meta["election_level"] == "state"
        assert meta["total_pages"] == 37
        assert meta["page_start"] == 1 and meta["page_end"] == 1

    def test_total_chunks_marks_the_whole_document(self) -> None:
        assert all(r.meta["total_chunks"] == 2 for r in _build())

    def test_none_valued_keys_are_dropped(self) -> None:
        meta = _build(chunks=[("Text.", None, None)], total_pages=None)[0].meta
        assert "page_start" not in meta and "total_pages" not in meta


# ===========================================================================
# Identity and change detection
# ===========================================================================


class TestIdentity:
    """Ids are deterministic, and cannot collide with the AW manifesto half."""

    def test_source_item_id_is_stable_across_builds(self) -> None:
        assert _build()[0].source_item_id == _build()[0].source_item_id

    def test_source_item_id_is_source_scoped(self) -> None:
        expected = compute_source_item_id(
            "party_manifesto", _PATH, source=UPLOAD_SOURCE
        )
        assert _build()[0].source_item_id == expected
        # An AW program id hashed WITHOUT the source discriminator is a different
        # point, so the two producers can never overwrite each other.
        assert expected != compute_source_item_id("party_manifesto", _PATH)

    def test_different_documents_get_different_ids(self) -> None:
        other = _PATH.replace("/spd/", "/cdu/")
        assert (
            _build()[0].source_item_id != _build(path=other, url=_URL)[0].source_item_id
        )


class TestContentHash:
    """The runner re-embeds only when the hash changes — so it must cover display."""

    def test_stable_for_identical_input(self) -> None:
        assert _build()[0].content_hash == _build()[0].content_hash

    def test_changes_when_text_changes(self) -> None:
        other = _build(chunks=[("Anderer Text.", 1, 1)])[0]
        assert (
            other.content_hash
            != _build(chunks=[("Erster Absatz.", 1, 1)])[0].content_hash
        )

    def test_changes_when_only_provenance_changes(self) -> None:
        # A corrected document date or a moved file must refresh the stored chunk;
        # otherwise the source card shows a stale date forever.
        moved = _PATH.replace("_2026-06-01", "_2026-06-02")
        assert _build(path=moved)[0].content_hash != _build()[0].content_hash

    def test_changes_when_the_region_changes(self) -> None:
        relocated = ElectionFixture(**{**FIXTURE.__dict__, "region": "DE-BY"})
        assert _build(fixture=relocated)[0].content_hash != _build()[0].content_hash


# ===========================================================================
# Validation
# ===========================================================================


def test_party_not_in_the_election_is_rejected() -> None:
    with pytest.raises(FixtureLookupError, match="not configured"):
        _build(path=_PATH.replace("/spd/", "/volt/"))


def test_empty_chunk_list_yields_no_records() -> None:
    assert _build(chunks=[]) == []
