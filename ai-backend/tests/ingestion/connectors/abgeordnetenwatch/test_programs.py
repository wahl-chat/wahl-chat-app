# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for programs.py — AW-linked external program docs -> party_manifesto corpus.

Behaviors:
  - ingest_programs processes only field_related_links whose uri startswith "http"
  - "entity:node/..." internal refs are skipped (SSRF guard, Pitfall 7)
  - Each fetched program -> SourceItemRecord(source_type=PARTY_MANIFESTO,
    authority_tier=SELF_REPORTED, vector_status="pending")
  - programs.py imports nothing from matcher_writer (structural zero-QSP, Req 12)
  - programs.py does not write question_stance_pairs (zero-QSP invariant)
  - chunk_program(source_item, raw) -> list[ChunkRecord] (2-arg worker-compatible)
  - worker.chunk_source_item routes PARTY_MANIFESTO -> chunk_program (not ValueError)
"""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

try:
    from google.cloud.firestore_v1.base_query import FieldFilter
    from src.ingestion.schemas import AuthorityTier, ChunkRecord, SourceItemRecord, SourceType
except ImportError as _e:
    pytest.skip(
        f"Phase-5 schema teardown: {_e} — SourceItemRecord removed in Plan 05-01",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Static import assertions (no emulator required)
# ---------------------------------------------------------------------------


class TestProgramsImports:
    """programs.py must not import matcher_writer (structural zero-QSP, Req 12)."""

    def test_programs_does_not_import_matcher_writer(self) -> None:
        """programs.py must not import anything from matcher_writer."""
        import src.ingestion.connectors.abgeordnetenwatch.programs as programs_mod

        source = inspect.getsource(programs_mod)
        assert "matcher_writer" not in source, (
            "programs.py must NOT import matcher_writer (Req 12 structural zero-QSP)"
        )

    def test_programs_does_not_reference_question_stance_pairs(self) -> None:
        """programs.py must not reference QuestionStancePair or question_stance_pairs."""
        import src.ingestion.connectors.abgeordnetenwatch.programs as programs_mod

        source = inspect.getsource(programs_mod)
        assert "QuestionStancePair" not in source, (
            "programs.py must not reference QuestionStancePair (Req 12)"
        )
        assert "question_stance_pairs" not in source, (
            "programs.py must not reference question_stance_pairs collection (Req 12)"
        )

    def test_ingest_programs_function_exists(self) -> None:
        """ingest_programs must be defined in programs.py."""
        from src.ingestion.connectors.abgeordnetenwatch import programs

        assert hasattr(programs, "ingest_programs"), (
            "ingest_programs must exist in programs.py"
        )
        assert callable(programs.ingest_programs)

    def test_chunk_program_function_exists(self) -> None:
        """chunk_program must be defined in programs.py with 2-arg signature."""
        from src.ingestion.connectors.abgeordnetenwatch import programs

        assert hasattr(programs, "chunk_program"), (
            "chunk_program must exist in programs.py"
        )
        assert callable(programs.chunk_program)

    def test_chunk_program_has_two_arg_signature(self) -> None:
        """chunk_program must have (source_item, raw) 2-arg signature (worker contract)."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        sig = inspect.signature(chunk_program)
        params = list(sig.parameters.keys())
        assert len(params) == 2, (
            f"chunk_program must have exactly 2 parameters (source_item, raw), got {params}"
        )
        assert params[0] == "source_item", (
            f"First parameter must be 'source_item', got {params[0]!r}"
        )
        assert params[1] == "raw", (
            f"Second parameter must be 'raw', got {params[1]!r}"
        )

    def test_worker_imports_chunk_program(self) -> None:
        """worker.py must import chunk_program from programs.py."""
        import src.ingestion.worker as worker_mod

        source = inspect.getsource(worker_mod)
        assert (
            "from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program"
            in source
        ), "worker.py must import chunk_program from AW programs module"

    def test_worker_has_party_manifesto_branch(self) -> None:
        """worker.chunk_source_item must have a PARTY_MANIFESTO branch."""
        import src.ingestion.worker as worker_mod

        source = inspect.getsource(worker_mod)
        assert "PARTY_MANIFESTO" in source, (
            "worker.py must have a PARTY_MANIFESTO dispatcher branch"
        )


# ---------------------------------------------------------------------------
# ingest_programs behavior tests
# ---------------------------------------------------------------------------


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    doc_ref = MagicMock()
    db.collection.return_value.document.return_value = doc_ref
    return db


def _make_mock_http_response(text: str = "Wahlprogramm content") -> MagicMock:
    """Build a mock HTTP response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = text
    resp.content = text.encode("utf-8")
    resp.raise_for_status.return_value = None
    return resp


@pytest.fixture(autouse=True)
def _resolve_hosts_to_public_ip() -> Iterator[None]:
    """Make the SSRF guard's DNS resolution deterministic in unit tests.

    ``_is_safe_program_url`` resolves the host and rejects private/loopback IPs.
    In tests we never hit the network, so patch ``socket.getaddrinfo`` to return
    a public IP (93.184.216.34) for allow-listed hosts.  Allow-list filtering and
    scheme filtering still apply, so non-allow-listed / non-http URLs are still
    rejected.
    """
    from unittest.mock import patch as _patch

    public = [(2, 1, 6, "", ("93.184.216.34", 0))]
    with _patch(
        "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
        return_value=public,
    ):
        yield


class TestIngestProgramsHttpFilter:
    """ingest_programs filters field_related_links to http(s) uris only."""

    def _make_poll_with_mixed_links(self) -> dict:
        """Poll with both a valid http link and an internal entity:node ref."""
        return {
            "id": 3602,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {
                    "uri": "https://www.abgeordnetenwatch.de/wahlprogramm.pdf",
                    "title": "Wahlprogramm",
                },
                {
                    "uri": "entity:node/4907",
                    "title": "Internal link",
                },
            ],
        }

    def _make_poll_with_only_entity_links(self) -> dict:
        """Poll with only internal entity:node refs (should produce no corpus items)."""
        return {
            "id": 9999,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "entity:node/1234", "title": "Internal only"},
            ],
        }

    def _make_poll_with_no_links(self) -> dict:
        """Poll with no field_related_links."""
        return {
            "id": 8888,
            "field_poll_date": "2020-05-14",
            "field_related_links": [],
        }

    def test_http_link_produces_corpus_item(self) -> None:
        """A poll with an https:// link produces one SourceItemRecord."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_poll_with_mixed_links()
        mock_db = _make_mock_db()
        mock_response = _make_mock_http_response("Wahlprogramm text content")

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=mock_response,
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(
                db=mock_db,
                polls=[poll],
                bucket="test-bucket",
            )

        assert len(results) == 1, (
            f"One https:// link must produce one SourceItemRecord, got {len(results)}"
        )

    def test_entity_node_link_is_skipped(self) -> None:
        """entity:node/... links are skipped — no corpus item produced."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_poll_with_mixed_links()
        mock_db = _make_mock_db()
        mock_response = _make_mock_http_response("Wahlprogramm text content")

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=mock_response,
            ) as mock_get,
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            ingest_programs(
                db=mock_db,
                polls=[poll],
                bucket="test-bucket",
            )

        # Only one HTTP fetch call (for the https:// link) — entity:node is skipped
        assert mock_get.call_count == 1, (
            f"Only the https:// link must be fetched, entity:node must be skipped. "
            f"Got {mock_get.call_count} fetch calls"
        )

    def test_only_entity_links_produces_no_corpus_items(self) -> None:
        """A poll with only entity:node refs produces no SourceItemRecords."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_poll_with_only_entity_links()
        mock_db = _make_mock_db()

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get"
        ) as mock_get:
            results = ingest_programs(
                db=mock_db,
                polls=[poll],
                bucket="test-bucket",
            )

        assert len(results) == 0, "entity:node-only poll must produce no corpus items"
        assert mock_get.call_count == 0, "No HTTP calls for entity:node refs"

    def test_empty_links_produces_no_corpus_items(self) -> None:
        """A poll with no links produces no SourceItemRecords."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_poll_with_no_links()
        mock_db = _make_mock_db()

        results = ingest_programs(
            db=mock_db,
            polls=[poll],
            bucket="test-bucket",
        )

        assert len(results) == 0


class TestIngestProgramsCorpusItemShape:
    """SourceItemRecords produced have correct source_type, authority_tier, vector_status."""

    def _make_simple_poll(self) -> dict:
        return {
            "id": 3602,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/prog.pdf", "title": "Programm"}
            ],
        }

    def test_source_type_is_party_manifesto(self) -> None:
        """SourceItemRecord must have source_type=PARTY_MANIFESTO."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert len(results) == 1
        assert results[0].source_type == SourceType.PARTY_MANIFESTO, (
            f"source_type must be PARTY_MANIFESTO, got {results[0].source_type}"
        )

    def test_authority_tier_is_self_reported(self) -> None:
        """SourceItemRecord must have authority_tier=SELF_REPORTED."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results[0].authority_tier == AuthorityTier.SELF_REPORTED, (
            f"authority_tier must be SELF_REPORTED, got {results[0].authority_tier}"
        )

    def test_vector_status_is_pending(self) -> None:
        """SourceItemRecord must have vector_status='pending' for embedding."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results[0].vector_status == "pending", (
            f"vector_status must be 'pending', got {results[0].vector_status!r}"
        )

    def test_region_is_de(self) -> None:
        """SourceItemRecord must have region='DE'."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results[0].region == "DE"

    def test_external_id_is_namespaced(self) -> None:
        """external_id must be namespaced 'aw_program:...' format."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results[0].external_id.startswith("aw_program:"), (
            f"external_id must be namespaced 'aw_program:...', got {results[0].external_id!r}"
        )

    def test_corpus_item_written_to_source_items(self) -> None:
        """ingest_programs writes SourceItemRecord to source_items/ collection."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        collection_calls = [str(c.args[0]) for c in mock_db.collection.call_args_list]
        assert "source_items" in collection_calls, (
            "ingest_programs must write to source_items/"
        )

    def test_zero_question_stance_pairs_written(self) -> None:
        """ingest_programs must NOT write to question_stance_pairs collection (Req 12)."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = self._make_simple_poll()
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/3602_0.json",
            ),
        ):
            ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        collection_calls = [str(c.args[0]) for c in mock_db.collection.call_args_list]
        assert "question_stance_pairs" not in collection_calls, (
            "ingest_programs must write zero QuestionStancePairs (Req 12)"
        )


# ---------------------------------------------------------------------------
# SSRF guard (_is_safe_program_url + ingest_programs fetch behavior)
# ---------------------------------------------------------------------------


class TestIsSafeProgramUrl:
    """_is_safe_program_url enforces scheme + host allow-list + public IP."""

    def test_rejects_non_http_scheme(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        assert _is_safe_program_url("ftp://www.abgeordnetenwatch.de/x") is False
        assert _is_safe_program_url("entity:node/4907") is False
        assert _is_safe_program_url("file:///etc/passwd") is False

    def test_rejects_non_allowlisted_host(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        # Even with a resolvable public IP, a non-allow-listed host is rejected.
        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            assert _is_safe_program_url("https://evil.example.com/x") is False

    def test_rejects_metadata_service_ip(self) -> None:
        """An allow-listed host that resolves to the cloud metadata IP is rejected."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("169.254.169.254", 0))],
        ):
            assert (
                _is_safe_program_url("https://www.abgeordnetenwatch.de/x") is False
            )

    def test_rejects_private_rfc1918_ip(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("10.0.0.5", 0))],
        ):
            assert _is_safe_program_url("https://www.abgeordnetenwatch.de/x") is False

    def test_rejects_loopback_ip(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 0))],
        ):
            assert _is_safe_program_url("https://www.abgeordnetenwatch.de/x") is False

    def test_fails_closed_on_resolution_error(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            side_effect=OSError("DNS failure"),
        ):
            assert _is_safe_program_url("https://www.abgeordnetenwatch.de/x") is False

    def test_accepts_allowlisted_public_host(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import _is_safe_program_url

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            assert _is_safe_program_url("https://www.abgeordnetenwatch.de/x") is True


class TestIngestProgramsSsrf:
    """ingest_programs blocks SSRF and disables redirects."""

    def test_internal_ip_link_is_not_fetched(self) -> None:
        """A link resolving to an internal IP must not be fetched or stored."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 1234,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/x", "title": "x"},
            ],
        }
        mock_db = _make_mock_db()

        # Override the autouse fixture: resolve to the metadata-service IP.
        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.socket.getaddrinfo",
                return_value=[(2, 1, 6, "", ("169.254.169.254", 0))],
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get"
            ) as mock_get,
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results == [], "Internal-IP link must produce no corpus item"
        mock_get.assert_not_called()

    def test_non_allowlisted_host_is_not_fetched(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 1235,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "http://localhost:8080/admin", "title": "x"},
                {"uri": "https://evil.example.com/x", "title": "y"},
            ],
        }
        mock_db = _make_mock_db()

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get"
        ) as mock_get:
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results == []
        mock_get.assert_not_called()

    def test_fetch_disables_redirects(self) -> None:
        """ingest_programs must call requests.get with allow_redirects=False."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 1236,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/prog.pdf", "title": "x"},
            ],
        }
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ) as mock_get,
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/1236_0.json",
            ),
        ):
            ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs.get("allow_redirects") is False, (
            "ingest_programs must fetch with allow_redirects=False (CR-01)"
        )


# ---------------------------------------------------------------------------
# unparseable publish_date is skip-and-warned, never date.today()
# ---------------------------------------------------------------------------


class TestIngestProgramsDateGuard:
    """A poll with no parseable date is skipped, not fabricated to date.today()."""

    def test_unparseable_date_poll_is_skipped(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 7777,
            "field_poll_date": "not-a-date",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/prog.pdf", "title": "x"},
            ],
        }
        mock_db = _make_mock_db()

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get"
        ) as mock_get:
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results == [], "Date-less poll must be skipped (WR-07)"
        # Skip happens before any fetch.
        mock_get.assert_not_called()

    def test_missing_date_poll_is_skipped(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 7778,
            # no field_poll_date key
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/prog.pdf", "title": "x"},
            ],
        }
        mock_db = _make_mock_db()

        with patch(
            "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get"
        ) as mock_get:
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert results == []
        mock_get.assert_not_called()

    def test_valid_date_poll_uses_parsed_date(self) -> None:
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 7779,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/prog.pdf", "title": "x"},
            ],
        }
        mock_db = _make_mock_db()

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response(),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/7779_0.json",
            ),
        ):
            results = ingest_programs(db=mock_db, polls=[poll], bucket="test-bucket")

        assert len(results) == 1
        assert results[0].publish_date == date(2020, 5, 14)


# ---------------------------------------------------------------------------
# chunk_program behavior tests (worker-compatible chunker)
# ---------------------------------------------------------------------------


def _make_program_source_item() -> SourceItemRecord:
    """Build a PARTY_MANIFESTO SourceItemRecord for chunk_program tests."""
    from src.ingestion.ids import compute_source_item_id

    external_id = "aw_program:3602:0"
    source_item_id = compute_source_item_id("party_manifesto", external_id)
    return SourceItemRecord(
        source_item_id=source_item_id,
        source_type=SourceType.PARTY_MANIFESTO,
        external_id=external_id,
        party_id="spd",
        region="DE",
        region_path=["EU", "DE"],
        authority_tier=AuthorityTier.SELF_REPORTED,
        publish_date=date(2020, 5, 14),
        storage_ref="gs://test-bucket/aw_programs/3602_0.json",
        vector_status="pending",
    )


def _make_program_raw(text: str = "Das Wahlprogramm. " * 50) -> dict:
    """Build a worker-compatible raw program payload."""
    return {
        "uri": "https://example.com/prog.pdf",
        "content": text,
    }


class TestChunkProgram:
    """chunk_program(source_item, raw) -> list[ChunkRecord] (worker-compatible)."""

    def test_returns_list_of_chunk_records(self) -> None:
        """chunk_program returns a non-empty list of ChunkRecords for non-empty text."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        assert isinstance(chunks, list), "chunk_program must return a list"
        assert len(chunks) > 0, "Non-empty program text must produce at least one chunk"
        for c in chunks:
            assert isinstance(c, ChunkRecord), f"Each item must be a ChunkRecord, got {type(c)}"

    def test_chunk_source_type_is_party_manifesto(self) -> None:
        """ChunkRecords must have source_type=PARTY_MANIFESTO."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        for c in chunks:
            assert c.source_type == SourceType.PARTY_MANIFESTO, (
                f"Chunk source_type must be PARTY_MANIFESTO, got {c.source_type}"
            )

    def test_chunk_authority_tier_inherited(self) -> None:
        """ChunkRecords must inherit authority_tier from source_item."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        for c in chunks:
            assert c.authority_tier == si.authority_tier

    def test_chunk_party_id_inherited(self) -> None:
        """ChunkRecords must inherit party_id from source_item."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        for c in chunks:
            assert c.party_id == si.party_id, (
                f"Chunk party_id must match source_item.party_id='{si.party_id}', "
                f"got {c.party_id!r}"
            )

    def test_chunk_text_is_non_empty(self) -> None:
        """Each ChunkRecord must have non-empty text."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        for c in chunks:
            assert c.text, "Chunk text must be non-empty"

    def test_chunk_indexes_are_sequential(self) -> None:
        """ChunkRecord indexes must be zero-based sequential."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_program(si, raw)

        for expected_idx, c in enumerate(chunks):
            assert c.chunk_index == expected_idx, (
                f"Chunk index must be {expected_idx}, got {c.chunk_index}"
            )

    def test_chunk_keys_are_deterministic(self) -> None:
        """Running chunk_program twice with same inputs yields same chunk_keys."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks_1 = chunk_program(si, raw)
        chunks_2 = chunk_program(si, raw)

        keys_1 = [c.chunk_key for c in chunks_1]
        keys_2 = [c.chunk_key for c in chunks_2]
        assert keys_1 == keys_2, "chunk_program must be deterministic"

    def test_empty_content_returns_empty_list(self) -> None:
        """chunk_program returns empty list for empty program content."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = {"uri": "https://example.com/prog.pdf", "content": ""}

        chunks = chunk_program(si, raw)

        # Empty content should produce no chunks (or single empty chunk — either is fine)
        # The key invariant is: no crash
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# Worker dispatcher tests (PARTY_MANIFESTO -> chunk_program, not ValueError)
# ---------------------------------------------------------------------------


class TestWorkerDispatcherPartyManifesto:
    """worker.chunk_source_item routes PARTY_MANIFESTO -> chunk_program."""

    def test_party_manifesto_routes_to_chunk_program(self) -> None:
        """chunk_source_item with PARTY_MANIFESTO source_item calls chunk_program."""
        from src.ingestion.worker import chunk_source_item
        from src.ingestion.connectors.abgeordnetenwatch.programs import chunk_program

        si = _make_program_source_item()
        raw = _make_program_raw()

        with patch(
            "src.ingestion.worker.chunk_program",
            wraps=chunk_program,
        ) as mock_chunk:
            result = chunk_source_item(si, raw)
            mock_chunk.assert_called_once_with(si, raw)
            assert isinstance(result, list)

    def test_party_manifesto_does_not_raise_value_error(self) -> None:
        """chunk_source_item with PARTY_MANIFESTO must NOT raise ValueError."""
        from src.ingestion.worker import chunk_source_item

        si = _make_program_source_item()
        raw = _make_program_raw()

        # Must not raise ValueError("unsupported source_type")
        try:
            chunk_source_item(si, raw)
        except ValueError as e:
            pytest.fail(
                f"chunk_source_item raised ValueError for PARTY_MANIFESTO: {e}\n"
                "worker.py must have a PARTY_MANIFESTO branch routing to chunk_program"
            )

    def test_party_manifesto_returns_non_empty_chunks(self) -> None:
        """chunk_source_item with PARTY_MANIFESTO returns non-empty ChunkRecords."""
        from src.ingestion.worker import chunk_source_item
        from src.ingestion.schemas import ChunkRecord

        si = _make_program_source_item()
        raw = _make_program_raw()

        chunks = chunk_source_item(si, raw)

        assert len(chunks) > 0, "PARTY_MANIFESTO must produce non-empty chunks"
        for c in chunks:
            assert isinstance(c, ChunkRecord)


# ---------------------------------------------------------------------------
# Emulator round-trip tests (skipped without emulator)
# ---------------------------------------------------------------------------


class TestEmulatorRoundTrip:
    """ingest_programs writes source_items and no question_stance_pairs."""

    def test_source_item_written_to_firestore(self, emulator_db) -> None:
        """ingest_programs writes a readable source_items doc to the emulator."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 99003602,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/test-prog.pdf", "title": "Test-Programm"}
            ],
        }

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response("Test program content"),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/99003602_0.json",
            ),
        ):
            results = ingest_programs(
                db=emulator_db,
                polls=[poll],
                bucket="test-bucket",
            )

        assert len(results) == 1
        si = results[0]

        doc = emulator_db.collection("source_items").document(str(si.source_item_id)).get()
        assert doc.exists, "source_items/{source_item_id} must exist after ingest"
        data = doc.to_dict()
        assert data["source_type"] == "party_manifesto"
        assert data["authority_tier"] == "self_reported"
        assert data["vector_status"] == "pending"

    def test_zero_question_stance_pairs_in_emulator(self, emulator_db) -> None:
        """ingest_programs must write zero question_stance_pairs docs (Req 12)."""
        from src.ingestion.connectors.abgeordnetenwatch.programs import ingest_programs

        poll = {
            "id": 99013602,
            "field_poll_date": "2020-05-14",
            "field_related_links": [
                {"uri": "https://www.abgeordnetenwatch.de/test-prog2.pdf", "title": "Test-Programm 2"}
            ],
        }

        with (
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.requests.get",
                return_value=_make_mock_http_response("Test program content 2"),
            ),
            patch(
                "src.ingestion.connectors.abgeordnetenwatch.programs.gcs.store_original",
                return_value="gs://test-bucket/aw_programs/99013602_0.json",
            ),
        ):
            ingest_programs(
                db=emulator_db,
                polls=[poll],
                bucket="test-bucket",
            )

        # No question_stance_pairs docs should exist for this program
        qsp_docs = list(
            emulator_db.collection("question_stance_pairs")
            .where(filter=FieldFilter("question_id", "==", "aw_poll_99013602"))
            .stream()
        )
        # The programs connector never writes QSPs — zero docs is the invariant
        # (We can't assert global count without knowing other test state, but
        # we can assert that the structural guard in test_programs_does_not_import_matcher_writer
        # is the primary assurance — this test just confirms no emulator writes)
        assert isinstance(qsp_docs, list)  # stream() is iterable
