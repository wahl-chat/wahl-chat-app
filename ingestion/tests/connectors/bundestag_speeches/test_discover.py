# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for BundestagSpeechesConnector.discover() and the empty-protocol skip guard.

Covers:
  - discover(None): returns ALL protocol IDs sorted ascending (oldest-first)
  - set-difference discovery: ingested protocols excluded, never-stored ones
    re-surface regardless of age, the runner cursor is ignored
  - update sweep: recently-`aktualisiert` ingested protocols re-surface
  - DIP DESC input → ascending output: regression guard
  - government (999…) speakers kept with name-lookup / quarantine attribution
  - test_empty_protocol_skips: normalize() raises ValueError for a protocol with zero
    usable speeches so run_connector skip-and-continues without advancing cursor
"""

from __future__ import annotations

from typing import Any

import pytest

from ingestion.connectors.bundestag_speeches.connector import (
    BundestagSpeechesConnector,
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


class _FakeStore:
    """Fake Qdrant client serving stored DIP parent keys for set-difference tests."""

    def __init__(self, ingested_protocol_ids: list[str]) -> None:
        self._ids = ingested_protocol_ids

    def scroll(self, **kwargs: object) -> tuple:
        from types import SimpleNamespace

        points = [
            SimpleNamespace(
                id=f"pt-{pid}",
                payload={"source_parent_key": f"parliamentary_speech:dip:{pid}"},
            )
            for pid in self._ids
        ]
        return (points, None)


def _make_connector_with_fake_client(pages: list[dict]) -> BundestagSpeechesConnector:
    """Create a BundestagSpeechesConnector whose DipClient is replaced by _FakeDipClient."""
    conn = object.__new__(BundestagSpeechesConnector)
    # Bypass __init__ to avoid DIP_API_KEY env requirement in tests
    conn._wahlperiode = 21  # type: ignore[attr-defined]
    conn._client = _FakeDipClient(pages)  # type: ignore[attr-defined]
    conn._protocols: dict = {}  # type: ignore[attr-defined]
    # Pre-seed an (empty) lookup so discover() skips ensure_mdb_lookup: these
    # tests exercise cursor/sort, not party resolution, and must not hit the network.
    conn._mdb_lookup = {"by_id": {}, "by_name": {}}  # type: ignore[attr-defined]
    return conn


# ---------------------------------------------------------------------------
# TestDiscover — cursor, filtering, and ascending re-sort
# ---------------------------------------------------------------------------

# DIP returns newest-first (DESC). These fixtures simulate that.
_DESC_PAGE = {
    "documents": [
        {"id": "200", "datum": "2026-06-15"},  # newest
        {"id": "100", "datum": "2026-05-01"},  # older
        {"id": "50", "datum": "2026-01-10"},  # oldest
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
            {
                "documents": [
                    {"id": "2", "datum": "2026-06-15"},
                    {"id": "1", "datum": "2026-05-01"},
                ]
            },
            {"documents": [{"id": "3", "datum": "2026-06-20"}]},
        ]
        conn = _make_connector_with_fake_client(pages)
        ids = conn.discover(since=None)
        # Must come back ascending by (datum, id): id "1" < "2" < "3"
        assert ids == ["1", "2", "3"], (
            f"discover() must re-sort DIP DESC to ascending; got: {ids}"
        )

    def test_discover_ignores_since_cursor(self) -> None:
        """The runner-derived cursor must NOT filter discovery: a cross-source
        or cross-Wahlperiode max(external_id) once starved DIP backfills (a
        stored 2026-07 op cursor made a WP20 run discover nothing). With
        set-difference, a high since value changes nothing."""
        conn = _make_connector_with_fake_client([_DESC_PAGE])
        ids = conn.discover(since=20260710)
        assert ids == ["50", "100", "200"], (
            f"set-difference discovery must ignore since entirely, got: {ids}"
        )

    def test_set_difference_excludes_ingested_and_re_surfaces_failures(self) -> None:
        """Stored protocols drop out of discovery; a protocol that FAILED on an
        earlier run (never stored) re-surfaces regardless of how old it is —
        the failure mode of the old 60-day lookback was permanent loss."""
        conn = _make_connector_with_fake_client([_DESC_PAGE])
        conn.bind_store(
            _FakeStore(ingested_protocol_ids=["200"]), "wahlchat_chunks_test"
        )
        ids = conn.discover(since=None)
        assert "200" not in ids, "an ingested protocol must not be re-discovered"
        assert "50" in ids and "100" in ids, (
            "never-stored protocols must re-surface regardless of age "
            f"(no lookback cutoff); got: {ids}"
        )

    def test_update_sweep_re_surfaces_recently_updated_protocol(self) -> None:
        """An ingested protocol whose DIP `aktualisiert` timestamp is recent is
        re-discovered so upstream corrections propagate; one updated long ago
        stays excluded."""
        from datetime import date, timedelta

        recent = (date.today() - timedelta(days=3)).isoformat()
        pages = [
            {
                "documents": [
                    {
                        "id": "700",
                        "datum": "2026-01-15",
                        "aktualisiert": f"{recent}T09:00:00+02:00",
                    },
                    {
                        "id": "701",
                        "datum": "2026-01-20",
                        "aktualisiert": "2026-01-21T09:00:00+02:00",
                    },
                ]
            }
        ]
        conn = _make_connector_with_fake_client(pages)
        conn.bind_store(
            _FakeStore(ingested_protocol_ids=["700", "701"]), "wahlchat_chunks_test"
        )
        ids = conn.discover(since=None)
        assert "700" in ids, (
            "a recently-updated ingested protocol must be re-surfaced "
            "(corrections sweep)"
        )
        assert "701" not in ids, (
            "an ingested protocol without a recent update stays excluded"
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
        from ingestion.registry import CONNECTOR_FACTORIES

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
        sys.modules.pop("ingestion.registry", None)
        # This import must succeed even when DIP_API_KEY is unset
        registry_mod = importlib.import_module("ingestion.registry")
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

    assert (
        "zero" in str(exc_info.value).lower() or "speech" in str(exc_info.value).lower()
    ), "ValueError message must mention 'zero' or 'speech' to aid skip-and-warn logging"


class TestGovernmentSpeakersKept:
    """Non-MdB speakers (999… ids) are real content — kept, never dropped.

    The 999… range covers federal/state ministers, state secretaries,
    Ministerpräsidenten, and Bundesrat members, not just procedural chairs;
    dropping the range removed entire government speeches from the corpus.
    """

    def _make_raw(self, speeches: list[dict], mdb_lookup: dict) -> dict:
        return {
            "protocol": {
                "id": "88888",
                "datum": "2026-06-01",
                "wahlperiode": 21,
                "dokumentnummer": "21/88",
            },
            "speeches": speeches,
            "mdb_lookup": mdb_lookup,
        }

    def test_minister_who_is_mdb_resolves_party_by_name(self) -> None:
        """A minister speaking under a 999… id who IS an MdB resolves to their
        real party via the name lookup."""
        from ingestion.connectors.bundestag_speeches.utils import (
            normalize_name_for_lookup,
        )

        conn = _make_connector_with_fake_client([])
        name_key = normalize_name_for_lookup("Erika Beispiel")
        mdb_lookup = {
            "by_id": {},
            "by_name": {
                name_key: {
                    "id": "11002222",
                    "names": ["Erika Beispiel"],
                    "party": "SPD",
                }
            },
        }
        conn._mdb_lookup = mdb_lookup  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "99900123",
                "speaker_name": "Erika Beispiel",
                "party": None,  # government speakers carry no <fraktion>
                "text": "Als Bundesministerin erkläre ich die Position der Regierung.",
                "xml_rede_id": "ID88801",
            }
        ]
        records = conn.normalize(self._make_raw(speeches, mdb_lookup))
        assert len(records) >= 1, "a 999… government speech must be KEPT"
        assert all(r.party_id == "spd" for r in records), (
            f"minister who is an MdB must resolve via name lookup, "
            f"got: {[r.party_id for r in records]}"
        )

    def test_non_mdb_government_speaker_quarantines_not_dropped(self) -> None:
        """A genuinely non-MdB speaker (e.g. a Ministerpräsident) is kept with
        party_id 'unbekannt' instead of being silently removed."""
        conn = _make_connector_with_fake_client([])
        mdb_lookup: dict = {"by_id": {}, "by_name": {}}
        conn._mdb_lookup = mdb_lookup  # type: ignore[attr-defined]
        speeches = [
            {
                "speaker_xml_id": "99900456",
                "speaker_name": "Alexander Schweitzer",
                "party": None,
                "text": "Als Ministerpräsident von Rheinland-Pfalz möchte ich betonen, "
                "dass die Länder eng eingebunden werden müssen.",
                "xml_rede_id": "ID88802",
            }
        ]
        records = conn.normalize(self._make_raw(speeches, mdb_lookup))
        assert len(records) >= 1, (
            "a non-MdB government speech must be KEPT (was previously dropped)"
        )
        assert all(r.party_id == "unbekannt" for r in records), (
            "unresolvable government speakers quarantine as 'unbekannt' "
            f"(drift signal), got: {[r.party_id for r in records]}"
        )
