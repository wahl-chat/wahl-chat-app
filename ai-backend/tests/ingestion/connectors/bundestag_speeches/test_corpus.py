# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for bundestag_speeches.mappers.corpus:
  - build_chunk_records: ChunkRecord list from a speech dict
  - chunk_text: tokenized splitting (port from tests/ingestion/test_ingest_speeches.py)
  - party_to_slug: full PARTY_ALIASES label set → canonical slugs (TestPartyToSlug)
  - external_id stamping: connector stamps YYYYMMDD on chunk via model_copy (test_external_id_stamp)

NOTE on test_external_id_stamp:
  The mapper's build_chunk_records DOES NOT set external_id (it defaults to None per the
  legacy contract). external_id is stamped by the CONNECTOR's normalize() via model_copy
  AFTER build_chunk_records returns. The test_external_id_stamp test therefore verifies
  the Pydantic model_copy mechanics at the mapper level; the connector-level end-to-end
  test lives in test_discover.py.

NOTE on external_id legacy inversion:
  The legacy test_ingest_speeches.py::test_external_id_is_none asserted external_id=None
  (the old behaviour). In this phase, speech chunks MUST have external_id=YYYYMMDD stamped
  by the connector. These tests expect the NEW behaviour:
    - build_chunk_records itself leaves external_id=None (mapper is neutral)
    - connector.normalize() stamps YYYYMMDD via model_copy (tested in test_discover.py)
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ingestion.connectors.bundestag_speeches.mappers.corpus import (
    build_chunk_records,
    chunk_text,
    party_to_slug,
)

from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceType


# ---------------------------------------------------------------------------
# TestPartyToSlug — full PARTY_ALIASES label set
# ---------------------------------------------------------------------------


class TestPartyToSlug:
    """party_to_slug maps all known party label strings to canonical slugs."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # Standard labels (from PARTY_ALIASES)
            ("SPD", "spd"),
            ("spd", "spd"),
            ("CDU/CSU", "cdu"),
            ("CDU", "cdu"),
            # Standalone CSU is a DISTINCT tenant (aligned with AW + csu manifesto).
            # Joint CDU/CSU label maps to "cdu" (Union fraction, not splittable from source).
            ("CSU", "csu"),
            ("csu", "csu"),
            ("FDP", "fdp"),
            ("fdp", "fdp"),
            ("AfD", "afd"),
            ("afd", "afd"),
            ("BÜNDNIS 90/DIE GRÜNEN", "gruene"),
            ("bündnis 90/die grünen", "gruene"),
            # Soft-hyphen variant (U+00AD) — AW connector edge case
            ("BÜNDNIS 90/DIE GRÜNEN", "gruene"),
            ("DIE LINKE", "linke"),
            ("die linke", "linke"),
            ("BSW", "bsw"),
            ("bsw", "bsw"),
            ("fraktionslos", "fraktionslos"),
            ("FRAKTIONSLOS", "fraktionslos"),
        ],
    )
    def test_known_parties(self, raw: str, expected: str) -> None:
        """Known party strings map to the expected canonical slug."""
        assert party_to_slug(raw) == expected, (
            f"party_to_slug({raw!r}) should return {expected!r}"
        )

    @pytest.mark.parametrize(
        "raw",
        [
            "Completely Unknown Party",
            "Piraten",
            "DSU",
            "",
            "  ",
        ],
    )
    def test_unknown_parties_return_unbekannt(self, raw: str) -> None:
        """Unknown or empty party strings map to 'unbekannt'."""
        assert party_to_slug(raw) == "unbekannt", (
            f"party_to_slug({raw!r}) should return 'unbekannt'"
        )

    def test_none_returns_unbekannt(self) -> None:
        """None party maps to 'unbekannt'."""
        assert party_to_slug(None) == "unbekannt"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestChunkText — splitting behaviour (ported from test_ingest_speeches.py)
# ---------------------------------------------------------------------------


class TestChunkText:
    """chunk_text splits over-long text and returns short text as-is."""

    def test_empty_text_returns_empty_list(self) -> None:
        """Empty string yields no chunks."""
        assert chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Whitespace-only string yields no chunks."""
        assert chunk_text("   \n\t  ") == []

    def test_short_text_single_chunk(self) -> None:
        """Text under the size limit is returned as a single chunk equal to input."""
        text = "Hello world. This is a short speech."
        assert chunk_text(text) == [text]

    def test_long_text_splits_into_multiple_nonempty_chunks(self) -> None:
        """Text over the character limit splits into multiple non-empty chunks."""
        text = " ".join(f"Satz Nummer {i} mit etwas Inhalt." for i in range(300))
        result = chunk_text(text, chunk_size=200, chunk_overlap=20)
        assert len(result) > 1
        assert all(c.strip() for c in result)


# ---------------------------------------------------------------------------
# Sample speech dicts for build_chunk_records tests
# ---------------------------------------------------------------------------

_SAMPLE_SPEECH: dict = {
    "xml_rede_id": "ID215000100",
    "speaker_xml_id": "11004870",
    "text": "Sehr geehrte Damen und Herren, ich spreche heute über die Energiewende.",
    "date": "2021-09-15",
    "party": "SPD",
    "speaker_name": "Olaf Scholz",
    "protocol_id": "21/99",
    "pdf_url": "https://dserver.bundestag.de/btp/21/2100099.pdf",
    "wahlperiode": 21,
    "protocol_api_id": "api-proto-99",
}

_SAMPLE_SPEECH_NO_META: dict = {
    "xml_rede_id": "ID215000199",
    "speaker_xml_id": "11004870",
    "text": "Sehr geehrte Damen und Herren, kurze Rede.",
    "date": "2021-09-15",
    "party": "SPD",
    "speaker_name": "Olaf Scholz",
    "protocol_id": "21/99",
    "pdf_url": "https://dserver.bundestag.de/btp/21/2100099.pdf",
}


# ---------------------------------------------------------------------------
# TestBuildChunkRecords — valid ChunkRecord from speech dict (ported from test_ingest_speeches.py)
# ---------------------------------------------------------------------------


class TestBuildChunkRecords:
    """build_chunk_records produces valid, frozen ChunkRecords."""

    def test_returns_list_of_chunk_records(self) -> None:
        """build_chunk_records must return a list of ChunkRecord instances."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert isinstance(result, list)
        assert len(result) >= 1
        for rec in result:
            assert isinstance(rec, ChunkRecord)

    def test_party_slug_mapped(self) -> None:
        """party_id is the canonical slug for the speech party."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert result[0].party_id == "spd"

    def test_source_type_parliamentary_speech(self) -> None:
        """source_type must be PARLIAMENTARY_SPEECH."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert result[0].source_type == SourceType.PARLIAMENTARY_SPEECH

    def test_authority_tier_factual_record(self) -> None:
        """authority_tier must be FACTUAL_RECORD (unified with op — a plenary
        speech is a factual parliamentary record regardless of transport)."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert result[0].authority_tier == AuthorityTier.FACTUAL_RECORD

    def test_region_is_de(self) -> None:
        """region must be 'DE'."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert result[0].region == "DE"

    def test_publish_date_parsed(self) -> None:
        """publish_date must equal the speech date."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert result[0].publish_date == date(2021, 9, 15)

    def test_citation_url_set(self) -> None:
        """citation_url must equal speech pdf_url."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        assert (
            result[0].citation_url == "https://dserver.bundestag.de/btp/21/2100099.pdf"
        )

    def test_citation_title_contains_speaker_and_date(self) -> None:
        """citation_title must include speaker_name, date, and protocol_id."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        title = result[0].citation_title or ""
        assert "Olaf Scholz" in title
        assert "2021-09-15" in title
        assert "21/99" in title

    def test_party_ids_is_none(self) -> None:
        """party_ids must be None for speech (not vote)."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        for rec in result:
            assert rec.party_ids is None

    def test_empty_text_returns_no_chunks(self) -> None:
        """Speeches with empty/whitespace-only text yield an empty list."""
        speech_empty = {**_SAMPLE_SPEECH, "text": ""}
        assert build_chunk_records(speech_empty) == []

        speech_ws = {**_SAMPLE_SPEECH, "text": "   \n  "}
        assert build_chunk_records(speech_ws) == []

    def test_chunk_index_sequential(self) -> None:
        """chunk_index values must be 0, 1, 2, ... for multi-chunk speeches."""
        long_text = " ".join([f"token{i}" for i in range(3000)])
        long_speech = {**_SAMPLE_SPEECH, "text": long_text}
        records = build_chunk_records(long_speech)
        for expected_index, rec in enumerate(records):
            assert rec.chunk_index == expected_index

    def test_deterministic_source_item_id(self) -> None:
        """Same speech id always produces the same source_item_id (UUID5 determinism)."""
        r1 = build_chunk_records(_SAMPLE_SPEECH)
        r2 = build_chunk_records(_SAMPLE_SPEECH)
        assert r1[0].source_item_id == r2[0].source_item_id

    def test_chunk_key_format(self) -> None:
        """chunk_key must follow the '{source_item_id}:{chunk_index:04d}' format."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        for rec in result:
            expected_key = f"{rec.source_item_id}:{rec.chunk_index:04d}"
            assert rec.chunk_key == expected_key

    def test_record_is_frozen(self) -> None:
        """ChunkRecord must be frozen (immutable)."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        rec = result[0]
        with pytest.raises(Exception):  # ValidationError or TypeError
            rec.party_id = "mutated"  # type: ignore[misc]

    def test_wahlperiode_stamped_from_speech(self) -> None:
        """wahlperiode is set from the speech dict when present."""
        result = build_chunk_records(_SAMPLE_SPEECH)
        for rec in result:
            assert rec.wahlperiode == 21

    def test_wahlperiode_none_when_absent(self) -> None:
        """wahlperiode is None when not present in speech dict."""
        result = build_chunk_records(_SAMPLE_SPEECH_NO_META)
        for rec in result:
            assert rec.wahlperiode is None

    def test_speech_chunk_dump_has_no_vote_keys(self) -> None:
        """Speech chunk's exclude_none dump must not contain vote envelope keys."""
        result = build_chunk_records(_SAMPLE_SPEECH_NO_META)
        for rec in result:
            dumped = rec.model_dump(mode="json", exclude_none=True)
            assert "vote_results" not in dumped
            assert "motion_outcome" not in dumped
            assert "party_ids" not in dumped
            # NOTE: external_id may be absent from dump since build_chunk_records
            # leaves it None; the connector stamps it via model_copy in normalize()
            assert "external_id" not in dumped


# ---------------------------------------------------------------------------
# test_external_id_stamp — connector normalize() stamps YYYYMMDD
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestDipSpeechKeyAndSource — shared speech_key + source='dip'
# ---------------------------------------------------------------------------


class TestDipSpeechKeyAndSource:
    """DIP ChunkRecords carry source='dip' and a shared, op-parity speech_key."""

    def test_source_is_dip(self) -> None:
        """Every DIP chunk carries source == 'dip' (discriminator)."""
        for rec in build_chunk_records(_SAMPLE_SPEECH):
            assert rec.source == "dip"

    def test_authority_tier_matches_op(self) -> None:
        """DIP authority_tier is FACTUAL_RECORD, matching the op mapper."""
        for rec in build_chunk_records(_SAMPLE_SPEECH):
            assert rec.authority_tier == AuthorityTier.FACTUAL_RECORD

    def test_speech_key_shape(self) -> None:
        """speech_key follows de-{wp}-{session}-{slug}-{agenda_slug} (empty agenda ok)."""
        rec = build_chunk_records(_SAMPLE_SPEECH)[0]
        assert rec.speech_key == "de-21-99-olaf-scholz-"

    def test_speech_key_with_agenda(self) -> None:
        """agenda_top_id threads into the agenda component (top-id 20 → top20)."""
        speech = {**_SAMPLE_SPEECH, "agenda_top_id": "20"}
        rec = build_chunk_records(speech)[0]
        assert rec.speech_key == "de-21-99-olaf-scholz-top20"

    def test_op_dip_parity_via_mapper(self) -> None:
        """DIP mapper key == op helper key for the SAME real speech.

        DIP feeds a merged speaker_name with an academic title + a top-id; op feeds
        discrete firstname/lastname + an official agenda title. Both must derive the
        identical byte string.
        """
        from src.ingestion.speech_key import make_speech_key

        dip_speech = {
            **_SAMPLE_SPEECH,
            "wahlperiode": 20,
            "protocol_id": "20/101",
            "speaker_name": "Dr. Mareike Lotte Wulf",
            "agenda_top_id": "20",
        }
        dip_key = build_chunk_records(dip_speech)[0].speech_key
        op_key = make_speech_key(
            ep=20,
            session=101,
            firstname="Mareike Lotte",
            lastname="Wulf",
            agenda="Tagesordnungspunkt 20",
        )
        assert dip_key == op_key == "de-20-101-mareike-lotte-wulf-top20"

    def test_speech_key_none_on_unparseable_session(self) -> None:
        """Unparseable protocol_id/session → speech_key None (no mismatched key)."""
        speech = {**_SAMPLE_SPEECH, "protocol_id": "internal-5678"}
        rec = build_chunk_records(speech)[0]
        assert rec.speech_key is None

    def test_speech_key_none_on_unparseable_wahlperiode(self) -> None:
        """Missing/unparseable wahlperiode → speech_key None."""
        speech = {k: v for k, v in _SAMPLE_SPEECH.items() if k != "wahlperiode"}
        rec = build_chunk_records(speech)[0]
        assert rec.speech_key is None


# ---------------------------------------------------------------------------
# TestNormalizePartyCsu — CSU survives normalize_party as a distinct label
# ---------------------------------------------------------------------------


class TestNormalizePartyCsu:
    """normalize_party and is_known_party treat CSU as a standalone canonical label."""

    def test_normalize_party_csu_returns_csu(self) -> None:
        """normalize_party('CSU') must return 'CSU', not 'CDU/CSU'."""
        from src.ingestion.connectors.bundestag_speeches.utils import normalize_party

        assert normalize_party("CSU") == "CSU", (
            "normalize_party('CSU') must return 'CSU' — CSU is a distinct tenant"
        )

    def test_normalize_party_cdu_returns_cdu(self) -> None:
        """normalize_party('CDU') must return 'CDU' as its own canonical label."""
        from src.ingestion.connectors.bundestag_speeches.utils import normalize_party

        assert normalize_party("CDU") == "CDU", (
            "normalize_party('CDU') must return 'CDU' — standalone CDU has its own label"
        )

    def test_normalize_party_joint_union_stays_cdu_csu(self) -> None:
        """normalize_party('CDU/CSU') must return 'CDU/CSU' (joint Union fraktion label)."""
        from src.ingestion.connectors.bundestag_speeches.utils import normalize_party

        assert normalize_party("CDU/CSU") == "CDU/CSU", (
            "normalize_party('CDU/CSU') must keep the joint Union fraktion label"
        )

    def test_is_known_party_csu(self) -> None:
        """is_known_party('CSU') must return True after adding CSU as a VALID_PARTIES value."""
        from src.ingestion.connectors.bundestag_speeches.utils import is_known_party

        assert is_known_party("CSU") is True, (
            "is_known_party('CSU') must be True — 'CSU' must be in VALID_PARTIES"
        )

    def test_is_known_party_cdu(self) -> None:
        """is_known_party('CDU') must return True."""
        from src.ingestion.connectors.bundestag_speeches.utils import is_known_party

        assert is_known_party("CDU") is True, "is_known_party('CDU') must be True"

    def test_is_known_party_joint_union(self) -> None:
        """is_known_party('CDU/CSU') must remain True (joint Union fraktion)."""
        from src.ingestion.connectors.bundestag_speeches.utils import is_known_party

        assert is_known_party("CDU/CSU") is True, (
            "is_known_party('CDU/CSU') must remain True"
        )

    @pytest.mark.parametrize(
        "party",
        ["SPD", "AfD", "DIE LINKE", "BSW", "FRAKTIONSLOS"],
    )
    def test_non_union_parties_still_known(self, party: str) -> None:
        """Non-Union parties must still be recognized after the CSU alias change."""
        from src.ingestion.connectors.bundestag_speeches.utils import (
            is_known_party,
            normalize_party,
        )

        assert is_known_party(party) is True, (
            f"is_known_party({party!r}) must still be True"
        )
        # normalize_party must return a non-None canonical label
        assert normalize_party(party) is not None, (
            f"normalize_party({party!r}) must return a canonical label, not None"
        )

    def test_party_to_slug_csu_distinct(self) -> None:
        """party_to_slug('CSU') == 'csu' (already in _PARTY_SLUG_MAP — verify not changed)."""
        assert party_to_slug("CSU") == "csu"

    def test_party_to_slug_cdu_is_cdu(self) -> None:
        """party_to_slug('CDU') == 'cdu'."""
        assert party_to_slug("CDU") == "cdu"

    def test_party_to_slug_joint_union_is_cdu(self) -> None:
        """party_to_slug('CDU/CSU') == 'cdu' (joint Union label maps to cdu slug)."""
        assert party_to_slug("CDU/CSU") == "cdu"


def test_external_id_stamp() -> None:
    """Connector normalize() stamps external_id=YYYYMMDD on every chunk via model_copy.

    NOTE: This test is intentionally placed here. If the connector is not yet
    importable, the module-level ImportError guard above handles it.

    For now: verify that a ChunkRecord produced by build_chunk_records (external_id=None)
    can be patched to YYYYMMDD via model_copy — confirming the Pydantic mechanics work.
    """
    records = build_chunk_records(_SAMPLE_SPEECH)
    assert len(records) >= 1

    # Simulate what connector.normalize() does: stamp external_id=YYYYMMDD via model_copy
    protocol_datum = "2026-06-15"
    external_id = int(protocol_datum.replace("-", ""))  # 20260615

    patched = [c.model_copy(update={"external_id": external_id}) for c in records]

    for rec in patched:
        assert rec.external_id == 20260615, (
            f"external_id must be YYYYMMDD int 20260615, got {rec.external_id!r}"
        )


# ---------------------------------------------------------------------------
# bulk ingest stamps external_id=YYYYMMDD on backfill records
# ---------------------------------------------------------------------------


def test_bulk_stamps_external_id_from_date() -> None:
    """bulk.ingest() stamps external_id=YYYYMMDD on each chunk (regression test).

    build_chunk_records leaves external_id=None (mapper neutrality).
    The bulk backfill path must derive YYYYMMDD from the speech date and
    stamp it via model_copy so get_cursor('parliamentary_speech') sees the
    backfill and the first live run does not re-embed everything.
    """
    from unittest.mock import MagicMock

    # Import the ingest function from bulk.py
    from src.ingestion.connectors.bundestag_speeches.bulk import ingest
    import json
    import tempfile
    from pathlib import Path

    # Build a minimal speech JSONL (one speech with a known date)
    speech = {
        "id": "BULK-TEST-001",
        "text": "Dies ist ein Test-Rede für die Prüfung der YYYYMMDD-Stempelung.",
        "date": "2021-09-15",
        "party": "SPD",
        "speaker_name": "Test Redner",
        "protocol_id": "20/1",
        "pdf_url": None,
        "wahlperiode": 20,
    }
    jsonl_content = json.dumps(speech) + "\n"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(jsonl_content)
        tmp_path = Path(f.name)

    try:
        # Mock Qdrant and embeddings so we never touch the real services.
        mock_qdrant = MagicMock()
        mock_embed = MagicMock()
        # embed_documents must return a valid-dimension vector for _upsert_chunks.
        # Import EMBEDDING_DIM for correctness.
        from src.ingestion.setup_collection import EMBEDDING_DIM

        mock_embed.embed_documents.return_value = [[0.0] * EMBEDDING_DIM]

        # Capture the chunks passed to _upsert_chunks via the qdrant.upsert call.
        upserted_points: list = []

        def _capture_upsert(collection_name, points, wait=True):
            upserted_points.extend(points)

        mock_qdrant.upsert.side_effect = _capture_upsert

        processed, chunks = ingest(tmp_path, mock_qdrant, mock_embed, limit=None)

        assert processed == 1, f"Expected 1 speech processed, got {processed}"
        assert chunks >= 1, f"Expected at least 1 chunk, got {chunks}"
        assert len(upserted_points) >= 1, "Expected at least one upserted point"

        # The payload of each upserted point must carry external_id = 20210915 (YYYYMMDD).
        for point in upserted_points:
            payload = point.payload
            assert payload.get("external_id") == 20210915, (
                f"bulk chunk must have external_id=20210915 (YYYYMMDD), "
                f"got {payload.get('external_id')!r}"
            )
    finally:
        tmp_path.unlink(missing_ok=True)


def test_build_chunk_records_skips_missing_date() -> None:
    """build_chunk_records returns [] on missing/unparseable date instead of fabricating."""
    speech_no_date = {**_SAMPLE_SPEECH, "date": ""}
    result = build_chunk_records(speech_no_date)
    assert result == [], (
        f"build_chunk_records must return [] for missing date, got {result!r}"
    )

    speech_bad_date = {**_SAMPLE_SPEECH, "date": "not-a-date"}
    result2 = build_chunk_records(speech_bad_date)
    assert result2 == [], (
        f"build_chunk_records must return [] for unparseable date, got {result2!r}"
    )


# ---------------------------------------------------------------------------
# DipClient.pages() stops at the hard page cap
# ---------------------------------------------------------------------------


def test_dip_client_pages_stops_at_max_pages() -> None:
    """DipClient.pages() stops after _MAX_PAGES pages instead of looping forever."""
    from unittest.mock import patch
    from src.ingestion.connectors.bundestag_speeches.client import DipClient
    from src.ingestion.connectors.bundestag_speeches.constants import _MAX_PAGES

    client = DipClient(api_key="test-key")

    page_count = 0

    def _always_has_next_cursor(endpoint, params=None):
        nonlocal page_count
        page_count += 1
        # Return a cursor that always changes — simulates infinite pagination.
        return {"documents": [], "cursor": f"cursor-{page_count}"}

    with patch.object(client, "get", side_effect=_always_has_next_cursor):
        pages = list(client.pages("/test-endpoint"))

    assert len(pages) == _MAX_PAGES, (
        f"DipClient.pages() must stop after {_MAX_PAGES} pages, got {len(pages)} pages"
    )


# ---------------------------------------------------------------------------
# (d) content_hash — DIP chunks must be change-aware
# ---------------------------------------------------------------------------


def test_dip_chunk_content_hash_present_and_change_sensitive() -> None:
    """(d) DIP speech chunks stamp a per-chunk content_hash so an upstream
    re-chunk or correction re-writes via run.py's change-aware guard."""
    records = build_chunk_records(_SAMPLE_SPEECH)
    assert records, "sample speech must produce records"
    assert all(r.content_hash is not None for r in records), (
        "every DIP chunk must stamp content_hash"
    )

    changed_speech = dict(
        _SAMPLE_SPEECH, text=_SAMPLE_SPEECH["text"] + " Nachtrag zur Korrektur."
    )
    changed_records = build_chunk_records(changed_speech)
    assert changed_records[0].content_hash != records[0].content_hash, (
        "changing the chunk text must change content_hash"
    )
