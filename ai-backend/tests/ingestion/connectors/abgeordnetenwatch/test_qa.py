# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for qa.py — AW Q&A HTML scrape -> qa_transcript corpus.

Behaviors:
  - scrape_qa(html, profile_slug) parses div.question blocks into Q&A tuples
  - Unanswered questions (.question__answer absent or "Antwort ausstehend") are skipped
  - Answered Q&A pairs -> SourceItemRecord(source_type=QA_TRANSCRIPT,
    authority_tier=SELF_REPORTED, vector_status="pending")
  - qa.py imports nothing from matcher_writer (structural zero-QSP, Req 13)
  - No users/{uid} path in qa.py (GDPR wall)
  - chunk_qa(source_item, raw) -> list[ChunkRecord] (2-arg worker-compatible)
  - worker.chunk_source_item routes QA_TRANSCRIPT -> chunk_qa (not ValueError)
"""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

try:
    from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceItemRecord, SourceType
except ImportError as _e:
    pytest.skip(
        f"Phase-5 schema teardown: {_e} — SourceItemRecord removed in Plan 05-01",
        allow_module_level=True,
    )

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_HTML_FIXTURE = _FIXTURES_DIR / "aw_qa_profile.html"

_PROFILE_SLUG = "tobias-lindner"

EMBEDDING_DIM = 3072


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture_html() -> str:
    """Load the saved Q&A profile HTML fixture."""
    return _HTML_FIXTURE.read_text(encoding="utf-8")


def _make_qa_source_item(
    question_slug: str = "was-planen-sie-fuer-die-energiewende",
    party_id: str = "gruene",
    publish_date: date | None = None,
) -> SourceItemRecord:
    """Build a minimal QA_TRANSCRIPT SourceItemRecord for chunker tests."""
    from src.ingestion.ids import compute_source_item_id

    external_id = f"aw_qa:{_PROFILE_SLUG}:{question_slug}"
    source_item_id = compute_source_item_id("qa_transcript", external_id)
    return SourceItemRecord(
        source_item_id=source_item_id,
        source_type=SourceType.QA_TRANSCRIPT,
        external_id=external_id,
        party_id=party_id,
        region="DE",
        region_path=["EU", "DE"],
        authority_tier=AuthorityTier.SELF_REPORTED,
        publish_date=publish_date or date(2022, 1, 15),
        vector_status="pending",
    )


def _make_raw_qa_pair(
    question_text: str = "Was planen Sie für die Energiewende?",
    answer_text: str = "Die Energiewende ist ein zentrales Projekt der Koalition.",
    questioner: str = "Max Mustermann",
    question_slug: str = "was-planen-sie-fuer-die-energiewende",
    profile_url: str = "https://www.abgeordnetenwatch.de/profile/tobias-lindner",
) -> dict:
    """Build a minimal raw Q&A pair dict (as stored to GCS by ingest_qa)."""
    return {
        "profile_slug": _PROFILE_SLUG,
        "question_slug": question_slug,
        "question_text": question_text,
        "questioner": questioner,
        "q_date": "12.01.2022",
        "answer_text": answer_text,
        "a_date": "15.01.2022",
        "profile_url": profile_url,
    }


# ---------------------------------------------------------------------------
# Static import assertions (no emulator required)
# ---------------------------------------------------------------------------


class TestQaImports:
    """qa.py must not import matcher_writer (structural zero-QSP, Req 13)."""

    def test_qa_does_not_import_matcher_writer(self) -> None:
        """qa.py must not import anything from matcher_writer."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        source = inspect.getsource(qa_mod)
        assert "matcher_writer" not in source, (
            "qa.py must NOT import matcher_writer (Req 13 structural zero-QSP)"
        )

    def test_qa_does_not_reference_question_stance_pairs(self) -> None:
        """qa.py must not reference QuestionStancePair or question_stance_pairs."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        source = inspect.getsource(qa_mod)
        assert "QuestionStancePair" not in source, (
            "qa.py must NOT reference QuestionStancePair (Req 13 structural zero-QSP)"
        )
        assert "question_stance_pairs" not in source, (
            "qa.py must NOT reference question_stance_pairs (Req 13 structural zero-QSP)"
        )

    def test_qa_does_not_access_users_collection(self) -> None:
        """qa.py must not access users/{uid} (GDPR Art. 9 wall)."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        source = inspect.getsource(qa_mod)
        # Exclude comment and docstring lines from check (grep pattern)
        code_lines = [
            line for line in source.splitlines()
            if not line.strip().startswith("#") and not line.strip().startswith('"""') and not line.strip().startswith("'''")
        ]
        for line in code_lines:
            assert 'collection("users")' not in line and 'users/{uid}' not in line, (
                f"qa.py must NOT access users/ collection (GDPR Art. 9 wall): {line!r}"
            )


# ---------------------------------------------------------------------------
# scrape_qa — HTML parsing (offline fixture)
# ---------------------------------------------------------------------------


class TestScrapeQa:
    """scrape_qa(html, profile_slug) parses answered Q&A pairs; skips unanswered."""

    def test_scrape_qa_returns_answered_pairs(self) -> None:
        """scrape_qa parses the fixture HTML and returns 3 answered Q&A pairs."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        # Fixture has 3 answered + 1 unanswered -> 3 pairs returned
        assert len(pairs) == 3, f"Expected 3 answered Q&A pairs, got {len(pairs)}"

    def test_scrape_qa_skips_unanswered_questions(self) -> None:
        """scrape_qa skips question blocks with 'Antwort ausstehend'."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        # None of the returned pairs should have "Antwort ausstehend" in answer
        for pair in pairs:
            assert "Antwort ausstehend" not in pair.get("answer_text", ""), (
                "scrape_qa must skip unanswered questions"
            )

    def test_scrape_qa_extracts_question_text(self) -> None:
        """scrape_qa extracts question text from .question__question a.h4."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        first_pair = pairs[0]
        assert "Energiewende" in first_pair["question_text"], (
            f"Expected question text to contain 'Energiewende', got: {first_pair['question_text']!r}"
        )

    def test_scrape_qa_extracts_answer_text(self) -> None:
        """scrape_qa extracts answer body text from .answer__body paragraphs."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        first_pair = pairs[0]
        assert first_pair["answer_text"], "answer_text must be non-empty for answered Q&As"
        assert "erneuerbaren Energien" in first_pair["answer_text"] or "Energiewende" in first_pair["answer_text"], (
            f"Expected answer text to contain energy-related terms, got: {first_pair['answer_text'][:100]!r}"
        )

    def test_scrape_qa_extracts_profile_slug(self) -> None:
        """scrape_qa sets profile_slug on each returned pair."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        for pair in pairs:
            assert pair["profile_slug"] == _PROFILE_SLUG, (
                f"Expected profile_slug={_PROFILE_SLUG!r}, got {pair['profile_slug']!r}"
            )

    def test_scrape_qa_extracts_question_slug(self) -> None:
        """scrape_qa extracts a question_slug from the question link href."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html = _load_fixture_html()
        pairs = scrape_qa(html, _PROFILE_SLUG)

        for pair in pairs:
            assert pair.get("question_slug"), "question_slug must be non-empty"
            assert "/" not in pair["question_slug"], (
                "question_slug must be the slug fragment only (no path separators)"
            )

    def test_scrape_qa_empty_html_returns_empty_list(self) -> None:
        """scrape_qa returns [] for HTML with no question blocks."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        pairs = scrape_qa("<html><body><p>No questions here.</p></body></html>", _PROFILE_SLUG)
        assert pairs == [], "scrape_qa must return [] for HTML with no question blocks"

    def test_scrape_qa_no_question_answer_div_skips(self) -> None:
        """scrape_qa skips question blocks with no .question__answer div."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import scrape_qa

        html_no_answer_div = """
        <div class="question">
          <div class="question__question">
            <a class="h4">Frage ohne Antwort-Div</a>
          </div>
        </div>
        """
        pairs = scrape_qa(html_no_answer_div, _PROFILE_SLUG)
        assert pairs == [], "question blocks with no .question__answer div must be skipped"


# ---------------------------------------------------------------------------
# scrape_qa function signature
# ---------------------------------------------------------------------------


class TestScrapeQaSignature:
    """def scrape_qa( must exist in qa.py (Req 13 acceptance criterion)."""

    def test_scrape_qa_function_defined(self) -> None:
        """qa.py must define a function named scrape_qa."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        assert hasattr(qa_mod, "scrape_qa"), "qa.py must define scrape_qa"
        assert callable(qa_mod.scrape_qa), "scrape_qa must be callable"


# ---------------------------------------------------------------------------
# chunk_qa — worker-compatible chunker (offline, no embedding)
# ---------------------------------------------------------------------------


class TestChunkQa:
    """chunk_qa(source_item, raw) -> list[ChunkRecord] (2-arg worker-compatible)."""

    def test_chunk_qa_function_defined(self) -> None:
        """qa.py must define a function named chunk_qa with 2-arg signature."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        assert hasattr(qa_mod, "chunk_qa"), "qa.py must define chunk_qa"
        assert callable(qa_mod.chunk_qa), "chunk_qa must be callable"

    def test_chunk_qa_returns_list_of_chunk_records(self) -> None:
        """chunk_qa returns a non-empty list of ChunkRecord instances."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        assert isinstance(chunks, list), "chunk_qa must return a list"
        assert len(chunks) > 0, "chunk_qa must return at least one chunk for non-empty Q&A"
        for chunk in chunks:
            assert isinstance(chunk, ChunkRecord), f"Each element must be ChunkRecord, got {type(chunk)}"

    def test_chunk_qa_chunks_have_correct_source_type(self) -> None:
        """chunk_qa chunks have source_type=QA_TRANSCRIPT."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for chunk in chunks:
            assert chunk.source_type == SourceType.QA_TRANSCRIPT, (
                f"chunk source_type must be QA_TRANSCRIPT, got {chunk.source_type}"
            )

    def test_chunk_qa_chunks_have_correct_authority_tier(self) -> None:
        """chunk_qa chunks have authority_tier=SELF_REPORTED."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for chunk in chunks:
            assert chunk.authority_tier == AuthorityTier.SELF_REPORTED, (
                f"chunk authority_tier must be SELF_REPORTED, got {chunk.authority_tier}"
            )

    def test_chunk_qa_chunks_have_non_empty_text(self) -> None:
        """chunk_qa chunks have non-empty text (text extracted by get_text, no raw HTML)."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for chunk in chunks:
            assert chunk.text.strip(), "Each chunk must have non-empty text"
            # Verify no raw HTML tags in chunk text
            assert "<p>" not in chunk.text and "<div>" not in chunk.text, (
                "chunk text must not contain raw HTML tags (T-04-17)"
            )

    def test_chunk_qa_inherits_party_id_from_source_item(self) -> None:
        """chunk_qa chunks inherit party_id from the source_item."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item(party_id="gruene")
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for chunk in chunks:
            assert chunk.party_id == "gruene", (
                f"chunk party_id must match source_item.party_id 'gruene', got {chunk.party_id!r}"
            )

    def test_chunk_qa_inherits_region_from_source_item(self) -> None:
        """chunk_qa chunks inherit region from the source_item."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for chunk in chunks:
            assert chunk.region == "DE", f"chunk region must be 'DE', got {chunk.region!r}"

    def test_chunk_qa_empty_raw_returns_empty_list(self) -> None:
        """chunk_qa returns [] when raw has no usable text."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = {"profile_slug": "tobias-lindner", "question_slug": "x", "question_text": "", "answer_text": ""}
        chunks = chunk_qa(si, raw)

        assert chunks == [], "chunk_qa must return [] for empty Q&A text"

    def test_chunk_qa_uses_zero_based_chunk_index(self) -> None:
        """chunk_qa produces chunks with zero-based sequential chunk_index."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i, (
                f"chunk_index must be {i}, got {chunk.chunk_index}"
            )

    def test_chunk_qa_chunk_key_contains_source_item_id(self) -> None:
        """chunk_qa chunk_key is formatted as '{source_item_id}:{chunk_index:04d}'."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()
        chunks = chunk_qa(si, raw)

        for i, chunk in enumerate(chunks):
            expected_key = f"{si.source_item_id}:{i:04d}"
            assert chunk.chunk_key == expected_key, (
                f"chunk_key must be {expected_key!r}, got {chunk.chunk_key!r}"
            )


# ---------------------------------------------------------------------------
# Worker dispatcher routing — QA_TRANSCRIPT -> chunk_qa
# ---------------------------------------------------------------------------


class TestWorkerQaTranscriptDispatcher:
    """worker.chunk_source_item routes QA_TRANSCRIPT -> chunk_qa (not ValueError)."""

    def test_worker_imports_chunk_qa(self) -> None:
        """worker.py must import chunk_qa from qa module."""
        import src.ingestion.worker as worker_mod
        import inspect

        source = inspect.getsource(worker_mod)
        assert "from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa" in source, (
            "worker.py must import chunk_qa from qa module (QA_TRANSCRIPT dispatcher branch)"
        )

    def test_worker_has_qa_transcript_branch(self) -> None:
        """worker.chunk_source_item must have a QA_TRANSCRIPT dispatcher branch."""
        import src.ingestion.worker as worker_mod
        import inspect

        source = inspect.getsource(worker_mod)
        assert "QA_TRANSCRIPT" in source, (
            "worker.py must reference QA_TRANSCRIPT in chunk_source_item (dispatcher branch)"
        )

    def test_qa_transcript_does_not_raise_value_error(self) -> None:
        """chunk_source_item with QA_TRANSCRIPT source_item routes to chunk_qa, not ValueError."""
        from src.ingestion.worker import chunk_source_item
        from src.ingestion.schemas import ChunkRecord

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()

        # This must NOT raise ValueError (which the fallthrough does)
        result = chunk_source_item(si, raw)
        assert isinstance(result, list), "chunk_source_item must return a list for QA_TRANSCRIPT"
        assert len(result) > 0, "chunk_source_item must return non-empty list for answered Q&A"
        for chunk in result:
            assert isinstance(chunk, ChunkRecord), "Each result element must be ChunkRecord"

    def test_qa_transcript_chunk_source_item_delegates_to_chunk_qa(self) -> None:
        """chunk_source_item delegates QA_TRANSCRIPT to chunk_qa."""
        from src.ingestion.worker import chunk_source_item
        from src.ingestion.connectors.abgeordnetenwatch.qa import chunk_qa

        si = _make_qa_source_item()
        raw = _make_raw_qa_pair()

        with patch(
            "src.ingestion.worker.chunk_qa",
            wraps=chunk_qa,
        ) as mock_chunk_qa:
            result = chunk_source_item(si, raw)
            mock_chunk_qa.assert_called_once_with(si, raw)
            assert isinstance(result, list)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Zero-QSP static assertion (Req 13 — structural guarantee)
# ---------------------------------------------------------------------------


class TestZeroQspInvariant:
    """qa.py must not write any QuestionStancePair records (Req 13 evidence-only invariant)."""

    def test_qa_module_has_no_qsp_import_strings(self) -> None:
        """qa.py source must not contain QSP-related module import strings."""
        import src.ingestion.connectors.abgeordnetenwatch.qa as qa_mod

        source = inspect.getsource(qa_mod)

        # These strings must never appear — structural proof of zero-QSP (Req 13)
        forbidden = [
            "matcher_writer",
            "QuestionStancePair",
            "question_stance_pairs",
        ]
        for token in forbidden:
            assert token not in source, (
                f"qa.py must NOT contain {token!r} (Req 13 structural zero-QSP guarantee)"
            )


# ---------------------------------------------------------------------------
# profile slug validation (path-traversal / injection guard)
# ---------------------------------------------------------------------------


class TestIngestQaSlugValidation:
    """ingest_qa validates profile slugs before building the pinned URL."""

    @pytest.mark.parametrize(
        "bad_slug",
        [
            "foo/../../some-other-path",
            "tobias.lindner",
            "tobias lindner",
            "foo%2e%2e",
            "../etc",
            "UPPER",  # uppercase not allowed by ^[a-z0-9-]+$
            "",
        ],
    )
    def test_invalid_slug_is_skipped_no_fetch(self, bad_slug: str) -> None:
        """An invalid slug is skipped: fetch is never called, no records written."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import ingest_qa

        mock_db = MagicMock()
        fetch = MagicMock(return_value="<html></html>")

        results = ingest_qa(
            db=mock_db,
            fetch=fetch,
            profile_slugs=[bad_slug],
            bucket="test-bucket",
        )

        assert results == [], f"invalid slug {bad_slug!r} must produce no records"
        fetch.assert_not_called()

    def test_valid_slug_is_fetched(self) -> None:
        """A valid slug passes the guard and the fetch is attempted."""
        from src.ingestion.connectors.abgeordnetenwatch.qa import ingest_qa

        mock_db = MagicMock()
        fetch = MagicMock(return_value="<html></html>")  # no question divs -> no pairs

        ingest_qa(
            db=mock_db,
            fetch=fetch,
            profile_slugs=["tobias-lindner"],
            bucket="test-bucket",
        )

        fetch.assert_called_once()
        called_url = fetch.call_args[0][0]
        assert called_url == (
            "https://www.abgeordnetenwatch.de/profile/tobias-lindner"
            "/fragen-antworten?answer=answered"
        )


# ---------------------------------------------------------------------------
# unparseable Q&A date is skip-and-warned, never date.today()
# ---------------------------------------------------------------------------


class TestQaDateGuard:
    """_parse_qa_date returns None on failure; ingest_qa skips date-less pairs."""

    def test_parse_qa_date_returns_none_on_failure(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.qa import _parse_qa_date

        assert _parse_qa_date("") is None
        assert _parse_qa_date("not-a-date") is None
        assert _parse_qa_date("15/01/2022") is None
        # Valid input still parses.
        assert _parse_qa_date("15.01.2022") == date(2022, 1, 15)

    def test_dateless_pair_is_skipped(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.qa import ingest_qa

        mock_db = MagicMock()
        fetch = MagicMock(return_value="<html>irrelevant</html>")

        # A scraped pair with no parseable a_date or q_date.
        dateless_pair = {
            "profile_slug": _PROFILE_SLUG,
            "question_slug": "no-date-question",
            "question_text": "Q?",
            "questioner": "X",
            "q_date": "",
            "answer_text": "A.",
            "a_date": "",
        }

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.qa.scrape_qa",
                return_value=[dateless_pair],
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.qa.gcs.store_original"
            ) as mock_store,
        ):
            results = ingest_qa(
                db=mock_db,
                fetch=fetch,
                profile_slugs=["tobias-lindner"],
                bucket="test-bucket",
            )

        assert results == [], "Date-less pair must be skipped (WR-07)"
        # Skip happens before GCS store / Firestore write.
        mock_store.assert_not_called()

    def test_dated_pair_is_written(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.qa import ingest_qa

        mock_db = MagicMock()
        fetch = MagicMock(return_value="<html>irrelevant</html>")

        dated_pair = {
            "profile_slug": _PROFILE_SLUG,
            "question_slug": "dated-question",
            "question_text": "Q?",
            "questioner": "X",
            "q_date": "12.01.2022",
            "answer_text": "A.",
            "a_date": "15.01.2022",
        }

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.qa.scrape_qa",
                return_value=[dated_pair],
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.qa.gcs.store_original",
                return_value="gs://test-bucket/aw_qa/tobias-lindner/dated-question.json",
            ),
        ):
            results = ingest_qa(
                db=mock_db,
                fetch=fetch,
                profile_slugs=["tobias-lindner"],
                bucket="test-bucket",
            )

        assert len(results) == 1
        assert results[0].publish_date == date(2022, 1, 15)
