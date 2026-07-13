# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for BundestagSpeechesConnector.discover() and the empty-protocol skip guard.

Covers:
  - discover(None): returns ALL protocol IDs sorted ascending (oldest-first)
  - discover(since=20260601): applies f.datum.start floor; filters protocols before that date
  - DIP DESC input → ascending output: regression guard
  - test_empty_protocol_skips: normalize() raises ValueError for a protocol with zero
    usable speeches so run_connector skip-and-continues without advancing cursor
"""

from __future__ import annotations

from typing import Any

import pytest

try:
    from src.ingestion.connectors.bundestag_speeches.connector import (  # noqa: F401
        BundestagSpeechesConnector,
    )
except ImportError as _e:
    pytest.skip(
        f"Wave 3 pending: connector.py not yet created — {_e}",
        allow_module_level=True,
    )


# ---------------------------------------------------------------------------
# Fake DIP client (mirrors abgeordnetenwatch test _stub_client idiom)
# ---------------------------------------------------------------------------


class _FakeDipClient:
    """Minimal DipClient stand-in for unit tests.

    pages() yields each dict from the provided list in order.
    DIP returns results DESCENDING by default; test inputs simulate that
    to verify the connector re-sorts them ASCENDING.
    """

    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages

    def pages(self, endpoint: str, params: dict) -> Any:  # noqa: ANN401
        yield from self._pages


def _make_connector_with_fake_client(pages: list[dict]) -> BundestagSpeechesConnector:
    """Create a BundestagSpeechesConnector whose DipClient is replaced by _FakeDipClient."""
    conn = object.__new__(BundestagSpeechesConnector)
    # Bypass __init__ to avoid DIP_API_KEY env requirement in tests
    conn._wahlperiode = 21  # type: ignore[attr-defined]
    conn._client = _FakeDipClient(pages)  # type: ignore[attr-defined]
    conn._protocols: dict = {}  # type: ignore[attr-defined]
    conn._mdb_lookup = None  # type: ignore[attr-defined]
    return conn


# ---------------------------------------------------------------------------
# TestDiscover — cursor, filtering, and ascending re-sort
# ---------------------------------------------------------------------------

# DIP returns newest-first (DESC). These fixtures simulate that.
_DESC_PAGE = {
    "documents": [
        {"id": "200", "datum": "2026-06-15"},  # newest
        {"id": "100", "datum": "2026-05-01"},  # older
        {"id": "50", "datum": "2026-01-10"},   # oldest
    ]
}


class TestDiscover:
    """BundestagSpeechesConnector.discover() re-sorts DIP DESC output to ASC."""

    def test_discover_none_returns_all_ascending(self) -> None:
        """discover(None) returns all protocol IDs sorted ascending (oldest-first)."""
        conn = _make_connector_with_fake_client([_DESC_PAGE])
        ids = conn.discover(since=None)
        assert ids == ["50", "100", "200"], (
            f"discover(None) must return ascending IDs, got: {ids}"
        )

    def test_discover_resorts_ascending_from_dip_desc_input(self) -> None:
        """DIP DESC input is re-sorted to ASC output (regression guard)."""
        # Provide two pages, each with DESC-ordered documents
        pages = [
            {"documents": [{"id": "2", "datum": "2026-06-15"}, {"id": "1", "datum": "2026-05-01"}]},
            {"documents": [{"id": "3", "datum": "2026-06-20"}]},
        ]
        conn = _make_connector_with_fake_client(pages)
        ids = conn.discover(since=None)
        # Must come back ascending by (datum, id): id "1" < "2" < "3"
        assert ids == ["1", "2", "3"], (
            f"discover() must re-sort DIP DESC to ascending; got: {ids}"
        )

    def test_discover_with_since_applies_lookback_floor(self) -> None:
        """discover(since=20260601) floors at since − LOOKBACK_DAYS (2026-04-02),
        NOT at the raw since date — a protocol that transiently failed below the
        max-external_id watermark must be re-discoverable within the window.

        With the fake page: id "200" (2026-06-15) and id "100" (2026-05-01, inside
        the 60-day lookback) remain; id "50" (2026-01-10, outside) is filtered.
        """
        conn = _make_connector_with_fake_client([_DESC_PAGE])
        ids = conn.discover(since=20260601)
        assert isinstance(ids, list)
        assert "200" in ids
        assert "100" in ids, (
            "a protocol dated within the lookback window (since − LOOKBACK_DAYS) "
            "must be re-discovered even though it is below the since watermark"
        )
        assert "50" not in ids, "protocols outside the lookback window stay excluded"
        # Every returned protocol respects the LOOKBACK floor of 2026-04-02.
        for pid in ids:
            protocol = conn._protocols.get(pid, {})  # type: ignore[attr-defined]
            datum = protocol.get("datum", "")
            if datum:
                assert datum >= "2026-04-02", (
                    f"Protocol {pid} with datum {datum!r} is before the lookback floor"
                )

    def test_lookback_re_discovers_failed_protocol(self) -> None:
        """(a) Regression: a protocol that failed on run 1 (below the resulting
        max external_id) is returned by discover() on run 2 via the lookback."""
        pages = [
            {
                "documents": [
                    {"id": "900", "datum": "2026-06-01"},  # succeeded run 1 → cursor 20260601
                    {"id": "899", "datum": "2026-05-20"},  # transiently FAILED run 1
                ]
            }
        ]
        conn = _make_connector_with_fake_client(pages)
        ids = conn.discover(since=20260601)
        assert "899" in ids, (
            "a failed protocol dated within LOOKBACK_DAYS of the cursor must be "
            "re-discovered on the next run"
        )

    def test_discover_caches_protocols(self) -> None:
        """discover() populates self._protocols with the fetched protocol dicts."""
        conn = _make_connector_with_fake_client([_DESC_PAGE])
        ids = conn.discover(since=None)
        # _protocols must be populated with each id
        for pid in ids:
            assert pid in conn._protocols  # type: ignore[attr-defined]

    def test_discover_returns_list(self) -> None:
        """discover() always returns a list, even for an empty DIP response."""
        conn = _make_connector_with_fake_client([{"documents": []}])
        ids = conn.discover(since=None)
        assert isinstance(ids, list)
        assert ids == []


# ---------------------------------------------------------------------------
# test_empty_protocol_skips — skip-and-warn via ValueError
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TestRegistry — bundestag_speeches registered in CONNECTOR_FACTORIES
# ---------------------------------------------------------------------------


class TestRegistry:
    """bundestag_speeches is registered in CONNECTOR_FACTORIES."""

    def test_bundestag_speeches_in_registry(self) -> None:
        """bundestag_speeches must appear in CONNECTOR_FACTORIES.

        NOTE: This test asserts membership ONLY — it does NOT invoke the factory.
        Calling the factory constructs BundestagSpeechesConnector which calls
        _require_dip_key(), which raises RuntimeError when DIP_API_KEY is unset.
        Membership test stays green in CI without a DIP key set.
        """
        from src.ingestion.registry import CONNECTOR_FACTORIES

        assert "bundestag_speeches" in CONNECTOR_FACTORIES, (
            "bundestag_speeches must be registered in CONNECTOR_FACTORIES"
        )

    def test_registry_import_has_no_side_effects(self) -> None:
        """Importing registry.py must not construct any connector.

        The deferred-import factory pattern ensures that importing the module
        does not trigger DIP_API_KEY lookup or any network calls.
        """
        import importlib
        import sys

        # Remove cached registry module to force a fresh import
        sys.modules.pop("src.ingestion.registry", None)
        # This import must succeed even when DIP_API_KEY is unset
        registry_mod = importlib.import_module("src.ingestion.registry")
        assert hasattr(registry_mod, "CONNECTOR_FACTORIES")
        # bundestag_speeches is a key — the factory itself is not called
        assert "bundestag_speeches" in registry_mod.CONNECTOR_FACTORIES


# ---------------------------------------------------------------------------
# TestCsuDisambiguation — Union/CDU/CSU fraktion → per-speaker party_id
# ---------------------------------------------------------------------------


class TestCsuDisambiguation:
    """Connector refines 'CDU/CSU' fraktion speeches to csu/cdu per MdB speaker."""

    # Minimal MdB lookup: one CSU record, one CDU/CSU record (joint-Union MdB)
    _MDB_LOOKUP = {
        "by_id": {
            "11000001": {
                "id": "11000001",
                "names": ["Franz Mayer"],
                "party": "CSU",
            },
            "11000002": {
                "id": "11000002",
                "names": ["Klaus Müller"],
                "party": "CDU/CSU",
            },
        },
        "by_name": {},
    }

    def _make_raw(self, speeches: list[dict]) -> dict:
        """Build a normalize()-compatible raw dict with the mini MdB lookup."""
        return {
            "protocol": {
                "id": "77777",
                "datum": "2026-06-01",
                "wahlperiode": 21,
                "fundstelle": {"pdf_url": None},
            },
            "speeches": speeches,
            "mdb_lookup": self._MDB_LOOKUP,
        }

    def test_union_speaker_resolving_to_csu_yields_csu_party_id(self) -> None:
        """Speech with <fraktion> CDU/CSU whose MdB resolves to CSU → party_id='csu'."""
        conn = _make_connector_with_fake_client([])
        conn._mdb_lookup = self._MDB_LOOKUP  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "11000001",  # CSU member
                "speaker_name": "Franz Mayer",
                "party": "CDU/CSU",  # fraktion tag (joint Union)
                "text": "Ich spreche fuer die CSU.",
                "xml_rede_id": "ID77001",
            }
        ]
        raw = self._make_raw(speeches)
        records = conn.normalize(raw)
        assert len(records) >= 1
        assert all(r.party_id == "csu" for r in records), (
            f"Expected party_id='csu' for all chunks, got: {[r.party_id for r in records]}"
        )

    def test_union_speaker_resolving_to_cdu_stays_cdu(self) -> None:
        """Speech with <fraktion> CDU/CSU whose MdB resolves to CDU/CSU → party_id='cdu'."""
        conn = _make_connector_with_fake_client([])
        conn._mdb_lookup = self._MDB_LOOKUP  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "11000002",  # CDU/CSU member (not CSU-only)
                "speaker_name": "Klaus Müller",
                "party": "CDU/CSU",  # fraktion tag
                "text": "Ich spreche fuer die Union.",
                "xml_rede_id": "ID77002",
            }
        ]
        raw = self._make_raw(speeches)
        records = conn.normalize(raw)
        assert len(records) >= 1
        assert all(r.party_id == "cdu" for r in records), (
            f"Expected party_id='cdu', got: {[r.party_id for r in records]}"
        )

    def test_non_union_speaker_unaffected_by_csu_refinement(self) -> None:
        """SPD speaker is not touched by CSU disambiguation; party_id stays 'spd'."""
        conn = _make_connector_with_fake_client([])
        conn._mdb_lookup = self._MDB_LOOKUP  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "11000003",  # not in MDB lookup at all
                "speaker_name": "Hans Schmidt",
                "party": "SPD",
                "text": "Die SPD spricht fuer Gerechtigkeit.",
                "xml_rede_id": "ID77003",
            }
        ]
        raw = self._make_raw(speeches)
        records = conn.normalize(raw)
        assert len(records) >= 1
        assert all(r.party_id == "spd" for r in records), (
            f"Expected party_id='spd', got: {[r.party_id for r in records]}"
        )

    def test_union_speaker_with_no_mdb_match_stays_cdu(self) -> None:
        """Union speaker with no MdB lookup match stays party_id='cdu' (no crash)."""
        conn = _make_connector_with_fake_client([])
        conn._mdb_lookup = self._MDB_LOOKUP  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "11009999",  # not in MDB lookup
                "speaker_name": "Unbekannter Redner",
                "party": "CDU/CSU",
                "text": "Meine Damen und Herren.",
                "xml_rede_id": "ID77004",
            }
        ]
        raw = self._make_raw(speeches)
        records = conn.normalize(raw)
        assert len(records) >= 1
        assert all(r.party_id == "cdu" for r in records), (
            f"Expected party_id='cdu' when MdB has no match, got: {[r.party_id for r in records]}"
        )


def test_empty_protocol_skips() -> None:
    """normalize() raises ValueError for a protocol with zero usable speeches.

    Verifies the skip-and-warn contract: run_connector catches ValueError,
    logs a WARNING, and does NOT advance the cursor for empty/garbage protocols.

    The raw dict passed to normalize() simulates a protocol whose speech list
    is empty (e.g. no <rede> nodes parsed, or all speeches had no text).
    """
    conn = _make_connector_with_fake_client([])

    # A raw payload with zero usable speeches
    empty_raw: dict = {
        "protocol": {"id": "99999", "datum": "2026-06-15", "wahlperiode": 21},
        "speeches": [],
        "mdb_lookup": {"by_id": {}, "by_name": {}},
    }

    with pytest.raises(ValueError, match="zero") as exc_info:
        conn.normalize(empty_raw)

    assert "zero" in str(exc_info.value).lower() or "speech" in str(exc_info.value).lower(), (
        "ValueError message must mention 'zero' or 'speech' to aid skip-and-warn logging"
    )
