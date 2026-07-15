# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for AbgeordnetenwatchVotesConnector — synchronous single-pass connector.

The connector implements the 3-method ABC
(discover/fetch/normalize) and returns list[ChunkRecord] from normalize().
All Firestore/GCS/matcher seam tests are removed.

Tests covered:
  1. normalize() returns list[ChunkRecord] with external_id=poll_id
  2. normalize() raises ValueError on zero-tally poll
  3. GDPR wall: no "users/" path in any AW module (static assertion)
  4. Registry: abgeordnetenwatch_votes registered; bundestag_votes deregistered (Req 8)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# D8: no ImportError skip guard — a broken connector import must FAIL the
# suite loudly, not turn it green with an "s".
from src.ingestion.connectors.abgeordnetenwatch.connector import (
    AbgeordnetenwatchVotesConnector,
)

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_poll_3602() -> dict:
    """Load the golden poll 3602 fixture as a raw payload dict."""
    poll_raw = json.loads((_FIXTURES_DIR / "aw_poll_3602_poll.json").read_text())
    votes_raw = json.loads((_FIXTURES_DIR / "aw_poll_3602_votes.json").read_text())
    poll = poll_raw["data"]  # single poll item
    votes = votes_raw["data"]  # list of vote items
    return {"poll": poll, "votes": votes}


def _make_zero_tally_raw() -> dict:
    """Build a raw payload where all votes have no-fraction (zero usable tallies)."""
    poll = {
        "id": 9999,
        "entity_type": "node",
        "label": "Test Poll Zero Tally",
        "abgeordnetenwatch_url": "https://www.abgeordnetenwatch.de/bundestag/19/abstimmungen/test",
        "field_legislature": {"id": 111, "label": "Bundestag 2017 - 2021"},
        "field_topics": [],
        "field_intro": None,
        "field_poll_date": "2020-05-14",
        "field_related_links": [],
    }
    # All votes have fraction=[] — zero usable tallies (Req 6 degenerate case)
    votes: list[dict[str, Any]] = [
        {"id": i, "vote": "no_show", "fraction": [], "mandate": None, "poll": {"id": 9999}}
        for i in range(5)
    ]
    return {"poll": poll, "votes": votes}


# ---------------------------------------------------------------------------
# Static GDPR-wall assertion
# ---------------------------------------------------------------------------


class TestGdprWall:
    """Static assertion: no AW module reads users/{uid}."""

    def test_no_users_path_in_aw_modules(self) -> None:
        """grep-based GDPR wall: no code accesses users/{uid} in any AW connector module.

        Comments mentioning users/ in a documentation context (e.g., explaining what NOT to do)
        are allowed.  Actual code paths that access Firestore users/ collection are not.
        We detect code access by looking for .collection("users") or ["users"] patterns,
        not bare 'users/' string mentions (which appear in security docstrings).
        """
        import os
        import re

        aw_src_dir = (
            Path(__file__).parents[4]
            / "src"
            / "ingestion"
            / "connectors"
            / "abgeordnetenwatch"
        )

        # Pattern for actual Firestore users collection access (not docstring mentions)
        _USERS_CODE_PATTERN = re.compile(
            r'\.collection\(["\']users["\']|db\[.?users|collection\("users'
        )

        found_violations: list[str] = []
        for root, _dirs, files in os.walk(str(aw_src_dir)):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(root) / fname
                text = fpath.read_text()
                for lineno, line in enumerate(text.splitlines(), 1):
                    # Skip comment lines and docstring mentions
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                        continue
                    if _USERS_CODE_PATTERN.search(line):
                        found_violations.append(f"{fpath.relative_to(aw_src_dir)}:{lineno}: {line.strip()}")

        assert not found_violations, (
            "GDPR Art.9 wall violation — code accesses users/ collection in AW modules:\n"
            + "\n".join(found_violations)
        )


# ---------------------------------------------------------------------------
# Registry tests (Req 8) — these do NOT need the emulator
# ---------------------------------------------------------------------------


class TestRegistry:
    """abgeordnetenwatch_votes registered; bundestag_votes deregistered; BundestagVoteConnector importable."""

    def test_abgeordnetenwatch_votes_in_registry(self) -> None:
        from src.ingestion.registry import CONNECTOR_FACTORIES

        assert "abgeordnetenwatch_votes" in CONNECTOR_FACTORIES, (
            "abgeordnetenwatch_votes must be registered in CONNECTOR_FACTORIES"
        )

    def test_bundestag_votes_not_in_registry(self) -> None:
        from src.ingestion.registry import CONNECTOR_FACTORIES

        assert "bundestag_votes" not in CONNECTOR_FACTORIES, (
            "bundestag_votes must be removed from CONNECTOR_FACTORIES (Req 8)"
        )


# ---------------------------------------------------------------------------
# normalize() returns list[ChunkRecord] with external_id=poll_id
# ---------------------------------------------------------------------------


class TestNormalize:
    """normalize() returns list[ChunkRecord]; external_id = raw poll_id int."""

    def test_normalize_returns_chunk_record_list(self) -> None:
        """normalize() must return list[ChunkRecord], not SourceItemRecord."""
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )
        from src.ingestion.schemas import ChunkRecord

        raw = _load_poll_3602()
        connector = AbgeordnetenwatchVotesConnector()

        result = connector.normalize(raw)

        assert isinstance(result, list), (
            "P5-INGEST-03: normalize() must return a list"
        )
        assert len(result) >= 1, (
            "P5-INGEST-03: normalize() must return at least one ChunkRecord for poll 3602"
        )
        assert all(isinstance(c, ChunkRecord) for c in result), (
            "P5-INGEST-03: every element in normalize() result must be a ChunkRecord"
        )

    def test_normalize_sets_external_id(self) -> None:
        """Every chunk.external_id must equal poll_id (3602 for poll 3602)."""
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()
        connector = AbgeordnetenwatchVotesConnector()

        chunks = connector.normalize(raw)

        for chunk in chunks:
            assert chunk.external_id == 3602, (
                f"P5-INGEST-03: chunk.external_id must be 3602 (raw int), got {chunk.external_id!r}"
            )

    def test_normalize_zero_tally_raises(self) -> None:
        """normalize() on a zero-tally poll raises ValueError (skip-and-warn path)."""
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _make_zero_tally_raw()
        connector = AbgeordnetenwatchVotesConnector()

        with pytest.raises(ValueError, match="zero usable tallies"):
            connector.normalize(raw)

    def test_normalize_stamps_wahlperiode_legislature_111(self) -> None:
        """normalize() stamps wahlperiode=19 for legislature_id=111 (19th Bundestag)."""
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()
        connector = AbgeordnetenwatchVotesConnector(legislature_id=111)

        chunks = connector.normalize(raw)
        for chunk in chunks:
            assert chunk.wahlperiode == 19, (
                f"legislature 111 must map to wahlperiode 19, got {chunk.wahlperiode!r}"
            )

    def test_normalize_stamps_wahlperiode_legislature_132(self) -> None:
        """normalize() stamps wahlperiode=20 for legislature_id=132 (20th Bundestag).

        The fixture poll is retagged to field_legislature.id=132 so the D12
        legislature cross-check passes (the golden fixture is a period-111 poll).
        """
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()
        raw["poll"] = dict(raw["poll"])
        raw["poll"]["field_legislature"] = {"id": 132, "label": "Bundestag 2021 - 2025"}
        connector = AbgeordnetenwatchVotesConnector(legislature_id=132)

        chunks = connector.normalize(raw)
        for chunk in chunks:
            assert chunk.wahlperiode == 20, (
                f"legislature 132 must map to wahlperiode 20, got {chunk.wahlperiode!r}"
            )

    def test_landtag_connector_stamps_wahlperiode_none(self) -> None:
        """normalize() stamps wahlperiode=None for Landtag legislature IDs (Pitfall 5).

        State Wahlperiode integers collide across states (Bayern 8th = some other state 8th),
        so Landtag chunks MUST NOT carry a wahlperiode int.  legislature_period_id is the
        sole period key for Landtage. Legislature 149 = Bayern 2023-2028.
        The fixture poll is retagged to field_legislature.id=149 so the D12
        legislature cross-check passes.
        """
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()
        raw["poll"] = dict(raw["poll"])
        raw["poll"]["field_legislature"] = {"id": 149, "label": "Bayern 2023 - 2028"}
        connector = AbgeordnetenwatchVotesConnector(legislature_id=149)

        chunks = connector.normalize(raw)
        for chunk in chunks:
            assert chunk.wahlperiode is None, (
                f"Landtag legislature 149 must yield wahlperiode=None (Pitfall 5), "
                f"got {chunk.wahlperiode!r}"
            )

    def test_normalize_raises_on_legislature_mismatch(self) -> None:
        """D12: normalizing a period-111 poll under a Bayern/149 connector must
        raise ValueError (skip-and-warn via the runner) instead of silently
        stamping region DE-BY on a Bundestag poll."""
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()  # fixture poll carries field_legislature.id=111
        connector = AbgeordnetenwatchVotesConnector(legislature_id=149)

        with pytest.raises(ValueError, match="legislature 111"):
            connector.normalize(raw)


def test_unknown_legislature_raises_value_error() -> None:
    """Constructing the connector with an id absent from LEGISLATURE_CONFIG raises ValueError.

    __init__ looks up legislature_id in LEGISLATURE_CONFIG and raises ValueError
    when the id is missing.
    """
    with pytest.raises(ValueError, match="LEGISLATURE_CONFIG"):
        AbgeordnetenwatchVotesConnector(legislature_id=9999)


# ---------------------------------------------------------------------------
# TestPollSinceFloor — AW_POLL_SINCE optional date floor in discover()
# ---------------------------------------------------------------------------


def _make_stub_polls() -> list[dict[str, Any]]:
    """Return a canned list of polls with varying dates and ids."""
    return [
        {"id": 100, "field_poll_date": "2019-12-15"},  # before 2020 floor
        {"id": 200, "field_poll_date": "2020-01-01"},  # exactly at floor
        {"id": 300, "field_poll_date": "2021-06-15"},  # after floor
        {"id": 400, "field_poll_date": ""},             # empty date — excluded when floor set
        {"id": 500, "field_poll_date": "2022-03-10"},  # after floor
    ]


class _MockQdrantEmpty:
    """Mock Qdrant client returning no existing chunks (first-run scenario)."""

    def scroll(self, **kwargs: Any) -> tuple:  # type: ignore[type-arg]
        return ([], None)


class _MockQdrantWithCursor:
    """Mock Qdrant client returning a single point to simulate a prior cursor."""

    def __init__(self, cursor_value: int) -> None:
        self._cursor = cursor_value

    def scroll(self, **kwargs: Any) -> tuple:  # type: ignore[type-arg]
        class _Pt:
            def __init__(self, ext_id: int) -> None:
                self.payload = {"external_id": ext_id}

        return ([_Pt(self._cursor)], None)


class TestPollSinceFloor:
    """AW_POLL_SINCE optional date-floor in discover()."""

    def _make_connector(self) -> "AbgeordnetenwatchVotesConnector":
        connector = AbgeordnetenwatchVotesConnector()
        return connector

    def _stub_client(self, connector: "AbgeordnetenwatchVotesConnector") -> None:
        """Monkeypatch connector._client so discover() never hits the network."""

        class _FakeClient:
            def get_all(self, endpoint: str, params: dict) -> list[dict]:  # type: ignore[override]
                # polls endpoint — return canned list
                return _make_stub_polls()

        connector._client = _FakeClient()  # type: ignore[assignment]

    def _stub_qdrant_empty(self, connector: "AbgeordnetenwatchVotesConnector") -> None:
        """Inject an empty Qdrant mock — simulates no prior chunks (leg_since=None)."""
        connector._qdrant = _MockQdrantEmpty()  # type: ignore[assignment]

    def _stub_qdrant_with_cursor(
        self, connector: "AbgeordnetenwatchVotesConnector", cursor: int
    ) -> None:
        """Inject a Qdrant mock that returns a per-legislature cursor (leg_since=cursor)."""
        connector._qdrant = _MockQdrantWithCursor(cursor)  # type: ignore[assignment]

    def test_floor_set_drops_old_polls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With AW_POLL_SINCE=2020-01-01, polls before 2020 and empty-date polls are dropped."""
        monkeypatch.setenv("AW_POLL_SINCE", "2020-01-01")

        connector = self._make_connector()
        self._stub_client(connector)
        self._stub_qdrant_empty(connector)  # no prior chunks → leg_since=None

        ids = connector.discover(since=None)

        # Expected: ids 200, 300, 500 (oldest-first). 100 (pre-2020) and 400 (empty) excluded.
        assert ids == ["200", "300", "500"], (
            f"Expected ['200', '300', '500'] but got {ids!r} — "
            "polls before 2020-01-01 and empty-date polls must be excluded"
        )

    def test_floor_unset_returns_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When AW_POLL_SINCE is unset, all polls are returned sorted by integer id."""
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)

        connector = self._make_connector()
        self._stub_client(connector)
        self._stub_qdrant_empty(connector)  # no prior chunks → leg_since=None

        ids = connector.discover(since=None)

        # All 5 polls returned, sorted ascending by INTEGER POLL ID (not by date).
        # Previously sorted by (field_poll_date, id); this aligns the sort axis with
        # the cursor axis (which walks on max(external_id)=max(poll_id)) so batch
        # truncation never permanently drops polls with large ids but early dates.
        assert set(ids) == {"100", "200", "300", "400", "500"}, (
            f"All 5 polls should be returned when floor is unset, got {ids!r}"
        )
        # Integer-id order: 100 < 200 < 300 < 400 < 500
        assert ids == ["100", "200", "300", "400", "500"], (
            f"FIX 1: Expected integer-id order ['100', '200', '300', '400', '500'], got {ids!r}"
        )

    def test_floor_set_with_cursor_filters_both(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Floor + per-legislature cursor: only polls with id > leg_since AND date >= floor survive.

        discover() ignores the global `since` arg in favour of the per-legislature cursor
        from _get_legislature_cursor() (Qdrant scroll).  This test simulates a prior
        Qdrant cursor of leg_since=200 so that only polls with id > 200 survive, then
        the AW_POLL_SINCE floor removes pre-2020 and empty-date polls.
        Remaining: id=300 (2021), id=500 (2022) — id=400 (empty date) excluded by floor.
        """
        monkeypatch.setenv("AW_POLL_SINCE", "2020-01-01")

        connector = self._make_connector()
        self._stub_client(connector)
        # Simulate prior run: max external_id = 200 for this legislature.
        self._stub_qdrant_with_cursor(connector, cursor=200)

        # The global since=200 is still passed to preserve the ABC contract; however
        # discover() uses leg_since=200 from the Qdrant mock, not the `since` arg.
        ids = connector.discover(since=200)

        assert ids == ["300", "500"], (
            f"Expected ['300', '500'] with ingested={{200}} + floor=2020-01-01, got {ids!r}"
        )

    def test_set_difference_resurfaces_polls_below_highest_ingested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Self-healing: a poll whose id is BELOW the highest already-ingested id must
        still be (re)discovered. A max(external_id) high-water mark (the previous design)
        would compute cursor=500 and permanently skip every poll with id <= 500 — the C1
        vote-loss bug. Set-difference re-surfaces the missing polls."""
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)

        connector = self._make_connector()
        self._stub_client(connector)
        # Only the highest poll (500) is ingested; 100-400 were skipped/failed earlier.
        self._stub_qdrant_with_cursor(connector, cursor=500)

        ids = connector.discover(since=None)

        assert ids == ["100", "200", "300", "400"], (
            "Polls below the highest ingested id must be re-surfaced by set-difference, "
            f"not permanently dropped by a max watermark; got {ids!r}"
        )


# ---------------------------------------------------------------------------
# Regression: discover() sorts by integer poll ID (not by field_poll_date)
# ---------------------------------------------------------------------------


def _make_mixed_polls() -> list[dict]:
    """Polls where sorting by date produces a different order than sorting by id.

    Poll 9999 has an EARLY date (2019-01-01) but a LARGE id.
    Poll 1 has a LATE date (2023-12-31) but a SMALL id.
    If discover() sorts by date, 9999 ends up at the HEAD — the cursor would
    advance past id=1 but never past id=9999, permanently dropping it on a
    batch-size-limited run.
    Sorting by integer id produces [1, 9999] — the correct batch-tail position.
    """
    return [
        {"id": 9999, "field_poll_date": "2019-01-01"},  # large id, early date
        {"id": 1,    "field_poll_date": "2023-12-31"},  # small id, late date
        {"id": 500,  "field_poll_date": "2021-06-15"},  # middle id, middle date
    ]


class TestDiscoverSortByPollId:
    """discover() must sort poll ids ascending by integer id, not by date."""

    def _make_connector(self) -> "AbgeordnetenwatchVotesConnector":
        connector = AbgeordnetenwatchVotesConnector()
        connector._qdrant = _MockQdrantEmpty()  # type: ignore[assignment]
        return connector

    def _stub_client_mixed(self, connector: "AbgeordnetenwatchVotesConnector") -> None:
        class _FakeClient:
            def get_all(self, endpoint: str, params: dict) -> list[dict]:  # type: ignore[override]
                return _make_mixed_polls()
        connector._client = _FakeClient()  # type: ignore[assignment]

    def test_sorts_by_integer_id_ascending(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """discover() returns ids sorted ascending by integer poll id."""
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)
        connector = self._make_connector()
        self._stub_client_mixed(connector)

        ids = connector.discover(since=None)

        # Integer-id sort: 1 < 500 < 9999 — NOT date sort (which would be: 9999, 500, 1)
        assert ids == ["1", "500", "9999"], (
            f"FIX 1: discover() must sort by integer poll id, got {ids!r}. "
            "Date-based sort would produce ['9999', '500', '1'] — wrong."
        )

    def test_batch_tail_holds_largest_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With batch_size truncation, the largest id ends up in the batch tail (not dropped)."""
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)
        connector = self._make_connector()
        self._stub_client_mixed(connector)

        ids = connector.discover(since=None)

        # batch[:2] includes ids 1 and 500; id 9999 is at the tail (index 2).
        # After processing the batch, the cursor advances to 500, so id 9999 is
        # picked up on the next run.  If sorted by date, id 9999 would be at index 0
        # of the batch and the cursor would advance past 1 — permanently dropping 500.
        batch_of_2 = ids[:2]
        assert "9999" not in batch_of_2, (
            "Largest id 9999 must sit in the TAIL, not the HEAD of the batch. "
            f"Got batch[:2]={batch_of_2!r}"
        )
        assert ids[-1] == "9999", (
            f"Largest id must be the last in ids list, got ids[-1]={ids[-1]!r}"
        )

    def test_normalize_raises_on_missing_date(self) -> None:
        """normalize() raises ValueError on unparseable/missing date instead of fabricating."""
        connector = AbgeordnetenwatchVotesConnector()

        # Build a raw payload with a poll that has no date but has valid votes.
        raw = _load_poll_3602()
        raw["poll"] = dict(raw["poll"])  # shallow copy
        raw["poll"]["field_poll_date"] = ""  # empty date

        with pytest.raises(ValueError, match="unparseable field_poll_date"):
            connector.normalize(raw)


# ---------------------------------------------------------------------------
# normalize() stamps legislature_period_id; per-legislature discover cursor
# ---------------------------------------------------------------------------


class TestNormalizeLegislaturePeriodId:
    """normalize() must stamp legislature_period_id on every chunk."""

    def test_normalize_stamps_legislature_period_id(self) -> None:
        """Every chunk from normalize() carries legislature_period_id == 111 for legislature 111.

        normalize() stamps legislature_period_id from config.
        """
        raw = _load_poll_3602()
        connector = AbgeordnetenwatchVotesConnector(legislature_id=111)

        chunks = connector.normalize(raw)

        assert len(chunks) >= 1, "normalize() must return at least one chunk for poll 3602"
        for chunk in chunks:
            assert chunk.legislature_period_id == 111, (
                f"Every chunk must have legislature_period_id=111 for legislature 111, "
                f"got {chunk.legislature_period_id!r}. "
                "Implement legislature_period_id stamping in normalize() (07-02)."
            )


class TestPerLegislatureCursor:
    """Per-legislature cursor: discover() must use _get_legislature_cursor() to scope to
    the current legislature's poll ID space, ignoring the global `since` from run_connector().
    """

    class _MockPoint:
        """Minimal mock for a Qdrant ScoredPoint with external_id in payload."""

        def __init__(self, external_id: int) -> None:
            self.payload = {"external_id": external_id}

    class _MockQdrant:
        """Mock Qdrant client: scroll returns a single point with external_id=30."""

        def scroll(self, **kwargs: Any) -> tuple:  # type: ignore[type-arg]
            return ([TestPerLegislatureCursor._MockPoint(30)], None)

    def _make_connector_149(self) -> "AbgeordnetenwatchVotesConnector":
        connector = AbgeordnetenwatchVotesConnector(legislature_id=149)
        return connector

    def _stub_client_with_bayern_polls(
        self, connector: "AbgeordnetenwatchVotesConnector"
    ) -> None:
        """Stub the AW client to return Bayern polls with IDs 50, 60, 70 (all < 5000)."""

        class _FakeBayernClient:
            def get_all(self, endpoint: str, params: dict) -> list:  # type: ignore[type-arg]
                # Bayern polls with low IDs that would be filtered out by a global since=5000
                return [
                    {"id": 50, "field_poll_date": "2024-01-15"},
                    {"id": 60, "field_poll_date": "2024-02-10"},
                    {"id": 70, "field_poll_date": "2024-03-20"},
                ]

        connector._client = _FakeBayernClient()  # type: ignore[assignment]

    def test_per_legislature_cursor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """discover(since=5000) for legislature 149 must still return Bayern polls.

        When the global cursor is 5000 (from high-ID Bundestag polls), a naive
        discover(since=5000) would filter out all Bayern polls (IDs 50-70 < 5000).
        The per-legislature cursor for legislature 149 is 30 (mocked Qdrant), so
        polls with id > 30 should be returned: 50, 60, 70.
        """
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)

        connector = self._make_connector_149()
        self._stub_client_with_bayern_polls(connector)

        # Pre-set the mock Qdrant so _get_qdrant() returns it when defined.
        connector._qdrant = self._MockQdrant()  # type: ignore[attr-defined]

        # Patch _get_qdrant on the connector instance (no-op if method doesn't exist yet).
        mock_qdrant = self._MockQdrant()
        try:
            monkeypatch.setattr(connector, "_get_qdrant", lambda: mock_qdrant)
        except AttributeError:
            pass  # _get_qdrant not defined — that is acceptable here

        # Global since=5000 from run_connector() would skip all Bayern polls.
        # The per-legislature cursor for legislature 149 returns external_id=30 from
        # the mocked Qdrant, so polls with id > 30 (i.e., 50, 60, 70) should be returned.
        ids = connector.discover(since=5000)

        assert ids == ["50", "60", "70"], (
            f"discover(since=5000) for legislature 149 returned {ids!r}; expected ['50', '60', '70']. "
            "The per-legislature cursor for id=149 is 30 (mocked), so polls with id > 30 must be "
            "discovered regardless of the global since=5000. "
            "Implement _get_legislature_cursor() in connector.py (07-02)."
        )


# ---------------------------------------------------------------------------
# normalize() stamps relevance_levels from field_topics.
# ---------------------------------------------------------------------------


class TestNormalizeRelevanceLevels:
    """normalize() stamps relevance_levels from field_topics taxonomy."""

    def test_normalize_stamps_relevance_levels(self) -> None:
        """A poll with field_topics [{label:'Verteidigung'}] yields chunks with
        relevance_levels == ['federal', 'state'].
        """
        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )

        raw = _load_poll_3602()
        raw = dict(raw)  # shallow copy of top-level dict
        raw["poll"] = dict(raw["poll"])  # shallow copy of poll dict
        raw["poll"]["field_topics"] = [{"id": 13, "label": "Verteidigung"}]

        connector = AbgeordnetenwatchVotesConnector()
        chunks = connector.normalize(raw)

        assert len(chunks) >= 1, "normalize() must return at least one chunk for poll 3602"
        for chunk in chunks:
            assert chunk.relevance_levels == ["federal", "state"], (
                f"Poll with Verteidigung topic must yield relevance_levels=['federal','state'], "
                f"got {chunk.relevance_levels!r}. "
                "Implement relevance_levels stamping in normalize() (08-02, P8-INGEST-01)."
            )

    def test_normalize_no_topics_defaults_all_levels(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A poll with field_topics=[] yields chunks with relevance_levels==
        ['federal','municipal','state'] and emits the no-topics warning.
        """
        import logging

        from src.ingestion.connectors.abgeordnetenwatch.connector import (
            AbgeordnetenwatchVotesConnector,
        )
        from src.ingestion.connectors.abgeordnetenwatch.topic_taxonomy_config import (
            ALL_LEVELS,
        )

        raw = _load_poll_3602()
        raw = dict(raw)  # shallow copy of top-level dict
        raw["poll"] = dict(raw["poll"])  # shallow copy of poll dict
        raw["poll"]["field_topics"] = []  # no topics → max-recall default

        connector = AbgeordnetenwatchVotesConnector()

        with caplog.at_level(logging.WARNING):
            chunks = connector.normalize(raw)

        assert len(chunks) >= 1, "normalize() must return at least one chunk"
        expected = sorted(ALL_LEVELS)  # ['federal', 'municipal', 'state']
        for chunk in chunks:
            assert chunk.relevance_levels == expected, (
                f"Poll with no field_topics must yield relevance_levels={expected!r} (D-05), "
                f"got {chunk.relevance_levels!r}. "
                "Implement relevance_levels stamping in normalize() (08-02, P8-INGEST-02)."
            )

        # the 'no field_topics' warning must appear in the log
        assert any("no field_topics" in rec.message for rec in caplog.records), (
            "D-05: logger.warning must be emitted for polls with no field_topics. "
            f"Captured log records: {[rec.message for rec in caplog.records]!r}"
        )


class TestDiscoverFailFast:
    """discover() must raise ValueError when the AW API returns zero polls."""

    def test_discover_fails_fast_on_zero_polls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """discover() raises ValueError when AW returns zero polls for the configured legislature.

        Zero polls from the API (before cursor filter) means the parliament_period_id
        in LEGISLATURE_CONFIG is wrong.  The fail-fast must trigger BEFORE the cursor
        filter so normal incremental runs (cursor up-to-date, filtered-to-empty) are
        not wrongly flagged.
        """
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)

        connector = AbgeordnetenwatchVotesConnector(legislature_id=111)

        class _EmptyPollClient:
            """Stub AW client that returns zero polls (simulates wrong parliament_period_id)."""

            def get_all(self, endpoint: str, params: dict) -> list:  # type: ignore[type-arg]
                return []  # zero polls — wrong period ID

        connector._client = _EmptyPollClient()  # type: ignore[assignment]

        # Legislature 111 started 2017-10-24 — far older than the grace window.
        with pytest.raises(ValueError, match="zero polls"):
            connector.discover(since=None)

    def test_discover_zero_polls_within_grace_window_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """D4: a legitimately NEW term (period started <= 90 days ago) with zero
        polls must NOT abort — warn and return [] instead."""
        import logging
        from datetime import date, timedelta

        from src.ingestion.connectors.abgeordnetenwatch import connector as conn_mod
        from src.ingestion.connectors.abgeordnetenwatch.legislature_config import (
            LEGISLATURE_CONFIG,
            LegislatureConfig,
        )

        monkeypatch.delenv("AW_POLL_SINCE", raising=False)
        # Register a synthetic just-started legislature (30 days old).
        recent_start = (date.today() - timedelta(days=30)).isoformat()
        monkeypatch.setitem(
            LEGISLATURE_CONFIG,
            999001,
            LegislatureConfig(999001, "DE-XX", "Testland 2026 - 2031", recent_start, None),
        )

        connector = AbgeordnetenwatchVotesConnector(legislature_id=999001)

        class _EmptyPollClient:
            def get_all(self, endpoint: str, params: dict) -> list:  # type: ignore[type-arg]
                return []

        connector._client = _EmptyPollClient()  # type: ignore[assignment]

        with caplog.at_level(logging.WARNING, logger=conn_mod.logger.name):
            result = connector.discover(since=None)

        assert result == [], "zero polls inside the grace window must return []"
        assert any("grace window" in r.message for r in caplog.records), (
            "the grace-window branch must log a warning"
        )


class TestDiscoverRefreshPath:
    """AW_REFRESH=1 discover path hygiene (D11)."""

    def test_refresh_path_filters_non_int_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The isinstance(id, int) filter must apply on the AW_REFRESH path too —
        a malformed poll entry must not crash sorting or leak a non-int id."""
        monkeypatch.delenv("AW_POLL_SINCE", raising=False)
        monkeypatch.setenv("AW_REFRESH", "1")

        connector = AbgeordnetenwatchVotesConnector(legislature_id=111)

        class _MalformedClient:
            def get_all(self, endpoint: str, params: dict) -> list:  # type: ignore[type-arg]
                return [
                    {"id": 100, "field_poll_date": "2020-05-14"},
                    {"id": "not-an-int", "field_poll_date": "2020-05-14"},
                    {"field_poll_date": "2020-05-14"},  # id missing entirely
                    {"id": 200, "field_poll_date": "2020-06-01"},
                ]

        connector._client = _MalformedClient()  # type: ignore[assignment]
        # AW_REFRESH skips the Qdrant set-difference — no Qdrant mock needed.

        ids = connector.discover(since=None)

        assert ids == ["100", "200"], (
            f"Refresh discover must keep only int-id polls, got {ids!r}"
        )
