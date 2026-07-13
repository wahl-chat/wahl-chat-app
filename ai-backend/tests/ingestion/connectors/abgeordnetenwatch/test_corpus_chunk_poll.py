# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Active tests for the vote-record array model: corpus.chunk_poll produces ONE
ChunkRecord per poll, embeds the subject only, and carries the tally in the
party_ids / vote_results payload (not in the embedded text).

These tests import only live symbols (no deleted matcher/SourceItemRecord),
so unlike test_mappers.py they are NOT skipped. Fixtures are loaded from disk like
test_connector.py.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src.ingestion.connectors.abgeordnetenwatch.mappers.corpus import (
    _canonical_party_slug,
    _normalize_fraction_label,
    chunk_poll,
)
from src.ingestion.ids import compute_source_item_id
from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class _SourceItemStub:
    """Minimal SourceItemLike stub (mirrors connector.normalize())."""

    def __init__(self) -> None:
        self.source_item_id = compute_source_item_id("vote_record", "3602")
        self.region = "DE"
        self.authority_tier = AuthorityTier.FACTUAL_RECORD
        self.source_type = SourceType.VOTE_RECORD
        self.publish_date = date(2020, 5, 14)


def _load_raw_3602() -> dict:
    poll = json.loads((_FIXTURES_DIR / "aw_poll_3602_poll.json").read_text())["data"]
    votes = json.loads((_FIXTURES_DIR / "aw_poll_3602_votes.json").read_text())["data"]
    return {"poll": poll, "votes": votes}


def _chunks() -> list[ChunkRecord]:
    return chunk_poll(_SourceItemStub(), _load_raw_3602())


def test_one_chunk_per_poll() -> None:
    """The array model collapses the 7-fraction poll to a single chunk."""
    chunks = _chunks()
    assert len(chunks) == 1
    assert isinstance(chunks[0], ChunkRecord)


def test_party_ids_lists_all_participants() -> None:
    chunk = _chunks()[0]
    assert set(chunk.party_ids or []) == {
        "fdp", "spd", "linke", "afd", "cdu", "gruene", "fraktionslos"
    }
    # party_id (tenant key) is the _all sentinel — votes opt out of tenant grouping.
    assert chunk.party_id == "_all"


def test_vote_results_one_entry_per_party_with_tally() -> None:
    chunk = _chunks()[0]
    # vote_results now lives in meta (envelope+meta split).
    meta = chunk.meta or {}
    results = meta.get("vote_results") or []
    assert len(results) == 7
    assert all(isinstance(r, dict) for r in results)
    # Every participating party in party_ids has a matching results entry.
    assert {r["party_id"] for r in results} == set(chunk.party_ids or [])
    # Stance is one of the locked derive_stance outputs.
    assert all(
        r["stance"] in {"agree", "disagree", "neutral", "absent"} for r in results
    )


def test_embed_text_is_subject_not_tally() -> None:
    """Subject (label + topics + intro) is embedded; the tally is NOT."""
    chunk = _chunks()[0]
    assert "Corona-Maßnahmen zum Schutz der Bevölkerung" in chunk.text
    # Topic labels are folded into the embed text to strengthen topic search.
    assert "Gesundheit" in chunk.text
    # The old tally template ("X Ja / Y Nein / ...") must not appear in the vector.
    assert "Ja /" not in chunk.text
    assert "Nein /" not in chunk.text


def test_motion_outcome_from_field_accepted() -> None:
    # Fixture poll 3602 has "field_accepted": true.
    # motion_outcome now lives in meta (envelope+meta split).
    chunk = _chunks()[0]
    meta = chunk.meta or {}
    assert meta.get("motion_outcome") == "angenommen"


def test_citation_fields_preserved() -> None:
    chunk = _chunks()[0]
    assert chunk.citation_title == "Corona-Maßnahmen zum Schutz der Bevölkerung"
    assert chunk.citation_url and chunk.citation_url.startswith("https://")


def test_vote_chunk_dump_has_no_speech_meta_keys() -> None:
    """A vote chunk's exclude_none dump must not contain SpeechMeta or pledge-only keys."""
    chunk = _chunks()[0]
    dumped = chunk.model_dump(mode="json", exclude_none=True)
    # SpeechMeta keys must not appear at the top level of a vote chunk.
    for speech_key in ("person_id", "speaker_name", "xml_rede_id", "protocol_id", "protocol_api_id"):
        assert speech_key not in dumped, (
            f"Vote chunk dump must not contain SpeechMeta key '{speech_key}'"
        )
    # Pledge-only envelope keys must not appear.
    for pledge_key in ("status", "as_of_date", "claim_id"):
        assert pledge_key not in dumped, (
            f"Vote chunk dump must not contain pledge-only key '{pledge_key}'"
        )
    # vote_results and motion_outcome must NOT appear at top-level (they live in meta).
    assert "vote_results" not in dumped, "vote_results must live in meta, not top-level"
    assert "motion_outcome" not in dumped, "motion_outcome must live in meta, not top-level"
    # They must appear inside meta.
    assert "meta" in dumped, "Vote chunk must have a meta dict"
    assert "vote_results" in dumped["meta"], "meta must contain vote_results"


def test_vote_chunk_party_ids_top_level() -> None:
    """party_ids must remain top-level (indexed envelope field) on a vote chunk."""
    chunk = _chunks()[0]
    dumped = chunk.model_dump(mode="json", exclude_none=True)
    assert "party_ids" in dumped, "party_ids must be top-level in vote chunk dump"
    assert isinstance(dumped["party_ids"], list)
    assert len(dumped["party_ids"]) > 0


def test_soft_hyphen_greens_label_maps_to_gruene() -> None:
    """Regression: AW returns the Greens fraction with a U+00AD soft hyphen
    ("BÜNDNIS 90/­DIE GRÜNEN"). A naive lowercase+strip lookup misses the
    map key and quarantines the whole Green fraction as "unbekannt" on every
    20th/21st-Bundestag vote. The normaliser must strip the soft hyphen so the
    label resolves to "gruene"."""
    soft_hyphen_label = "BÜNDNIS 90/­DIE GRÜNEN"
    assert "­" in soft_hyphen_label  # guard: the bug only exists with it
    assert _canonical_party_slug(soft_hyphen_label) == "gruene"
    # also with the parliament-period parenthetical AW puts on vote labels
    assert (
        _canonical_party_slug("BÜNDNIS 90/­DIE GRÜNEN (Bundestag 2021 - 2025)")
        == "gruene"
    )


def test_normalize_fraction_label_strips_invisible_chars() -> None:
    """_normalize_fraction_label removes zero-width/soft-hyphen chars, collapses
    whitespace, strips and lowercases."""
    assert _normalize_fraction_label("BÜNDNIS 90/­DIE GRÜNEN") == "bündnis 90/die grünen"
    assert _normalize_fraction_label("  FDP​ ") == "fdp"


# ---------------------------------------------------------------------------
# State-party slug map extension
# These tests cover _AW_FRACTION_SLUG_MAP additions for Landtag fractions.
# ---------------------------------------------------------------------------


class TestStatePartySlugMap:
    """Additions to _AW_FRACTION_SLUG_MAP for state-level parties.

    AW fraction labels include a parliament-period parenthetical suffix
    (e.g. "Freie Wähler (Bayern 2023 - 2028)") that `_canonical_party_slug`
    strips before looking up in the map.  These tests verify that the
    stripped base names resolve to canonical slugs matching the manifesto map
    (so retrieval returns both vote and manifesto chunks for the same party).
    """

    def test_freie_waehler_resolves_to_fw(self) -> None:
        """'Freie Wähler (Bayern 2023 - 2028)' must resolve to 'fw'."""
        assert _canonical_party_slug("Freie Wähler (Bayern 2023 - 2028)") == "fw"

    def test_ssw_resolves_to_ssw(self) -> None:
        """'SSW (Schleswig-Holstein 2022 - 2027)' must resolve to 'ssw'."""
        assert _canonical_party_slug("SSW (Schleswig-Holstein 2022 - 2027)") == "ssw"

    def test_bvb_fw_resolves_to_bvb_fw(self) -> None:
        """'BVB/Freie Wähler (Brandenburg 2024 - 2029)' must resolve to 'bvb-fw'."""
        assert _canonical_party_slug("BVB/Freie Wähler (Brandenburg 2024 - 2029)") == "bvb-fw"

    def test_unknown_fraction_quarantined_as_unbekannt(self) -> None:
        """Unknown fraction labels must return the quarantine slug 'unbekannt'."""
        assert _canonical_party_slug("Irgendeine Unbekannte Fraktion") == "unbekannt"

    def test_csu_regression_unchanged(self) -> None:
        """CSU must still resolve to 'csu' after the map extension (regression)."""
        assert _canonical_party_slug("CSU") == "csu"


def test_region_for_period_aw_labels() -> None:
    """region_for_period() resolves AW parliament_period labels to ISO 3166-2 codes.

    AW Landtag period labels use the form 'State YYYY - YYYY' (space before year,
    no 'Wahl' prefix), e.g. 'Bayern 2023 - 2028'.  region_for_period() must handle
    this form without modification.
    """
    from src.ingestion.connectors.manifestos.mappers.corpus import region_for_period

    assert region_for_period("Bayern 2023 - 2028") == "DE-BY"
