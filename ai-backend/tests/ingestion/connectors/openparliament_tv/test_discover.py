# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for OpenParliamentTvConnector.discover() — basename enumeration + lookback
(D-01/D-08/Q3) and the C5 descending early stop.

The client contract is basenames only (``YYYYY-session.json``) — the former
int/direct-ext fast path served only test fakes and was deleted (C13); the
fakes here return basenames, matching OpTvClient.list_session_files().
"""

from __future__ import annotations

import pytest

# Wave-0 guard: SKIP until the op connector exists.
connector_mod = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.connector",
    reason="op connector not yet implemented (later wave) — Wave-0 scaffold",
)

OpenParliamentTvConnector = getattr(connector_mod, "OpenParliamentTvConnector")


class _FakeOpBasenameClient:
    """Op-bulk client stand-in enumerating basename session files.

    Mirrors OpTvClient: list_session_files() → basenames;
    fetch_session_json(name) → JSON:API dict. Records fetches so the C5
    early-stop can be asserted.
    """

    def __init__(self, sessions: dict[str, dict]) -> None:
        self._sessions = sessions
        self.fetched: list[str] = []

    def list_session_files(self) -> list[str]:
        return list(self._sessions)

    def fetch_session_json(self, name: str) -> dict:
        self.fetched.append(name)
        return self._sessions[name]


def _session(date_start: str, title: str = "Sitzung") -> dict:
    return {"data": [{"dateStart": date_start, "title": title}]}


def _make_connector(sessions: dict[str, dict]):
    """Build an OpenParliamentTvConnector with __init__ bypassed (no network)."""
    conn = object.__new__(OpenParliamentTvConnector)
    conn._client = _FakeOpBasenameClient(sessions)  # type: ignore[attr-defined]
    return conn


def test_lookback_realigns() -> None:
    """Q3/D-08: discover() re-scans below the prior cursor by the LOOKBACK window.

    Prior op cursor advanced to 20230601 (a later-dated speech aligned first).
    An earlier session dated 2023-05-01 only just aligned — it sits BELOW the
    cursor. With a forward-only floor it would be stranded forever; with the
    `since − LOOKBACK (≥60 days)` floor it is re-picked.
    """
    sessions = {
        "20098-session.json": _session("2023-05-01T09:00:00+02:00"),
        "20099-session.json": _session("2023-06-01T09:00:00+02:00"),
        "20100-session.json": _session("2023-06-15T09:00:00+02:00"),
    }
    conn = _make_connector(sessions)

    discovered = conn.discover(since=20230601)

    assert "20098-session.json" in discovered, (
        "an out-of-order newly-aligned session below the cursor must be re-picked "
        "via the lookback floor (since − LOOKBACK)"
    )
    assert set(discovered) == set(sessions)


def test_discover_stops_fetching_below_the_floor() -> None:
    """C5: discover() iterates basenames DESCENDING (basename order is monotone
    in date) and stops fetching once a fetched session's ext < floor — the
    previous full-corpus scan fetched every WP20+21 session JSON per run."""
    sessions = {
        "20001-session.json": _session("2023-01-10T09:00:00+01:00"),  # far below floor
        "20002-session.json": _session("2023-02-10T09:00:00+01:00"),  # below floor
        "20099-session.json": _session("2023-05-20T09:00:00+02:00"),
        "20100-session.json": _session("2023-06-01T09:00:00+02:00"),
    }
    conn = _make_connector(sessions)

    # since=20230701 → floor = 2023-05-02 (60-day lookback).
    discovered = conn.discover(since=20230701)

    assert discovered == ["20099-session.json", "20100-session.json"]
    client = conn._client  # type: ignore[attr-defined]
    assert "20001-session.json" not in client.fetched, (
        "after the first below-floor session the scan must STOP — older basenames "
        "are never fetched"
    )
    # The stop is triggered by the first below-floor fetch (20002); 20001 is skipped.
    assert client.fetched == [
        "20100-session.json",
        "20099-session.json",
        "20002-session.json",
    ]


def test_discover_since_none_fetches_all() -> None:
    """C5: the full backfill (since=None) still fetches every session file."""
    sessions = {
        "20001-session.json": _session("2023-01-10T09:00:00+01:00"),
        "20100-session.json": _session("2023-06-01T09:00:00+02:00"),
    }
    conn = _make_connector(sessions)

    discovered = conn.discover(since=None)

    assert discovered == ["20001-session.json", "20100-session.json"]
    assert set(conn._client.fetched) == set(sessions)  # type: ignore[attr-defined]


def test_discover_returns_ascending_by_date() -> None:
    """Handles come back oldest-first (cursor order) despite the descending scan."""
    sessions = {
        "20100-session.json": _session("2023-06-01T09:00:00+02:00"),
        "20099-session.json": _session("2023-05-20T09:00:00+02:00"),
        "20101-session.json": _session("2023-06-15T09:00:00+02:00"),
    }
    conn = _make_connector(sessions)

    discovered = conn.discover(since=None)

    assert discovered == [
        "20099-session.json",
        "20100-session.json",
        "20101-session.json",
    ]


def test_same_date_sessions_both_discovered_and_fetchable() -> None:
    """(f) Two sessions whose earliest dateStart falls on the SAME calendar date
    must BOTH appear in discover() output and both be fetchable — previously the
    str(ext) cache key collided and one session's speeches were never ingested."""
    sessions = {
        "20101-session.json": {
            "data": [{"dateStart": "2023-04-28T09:00:00+02:00", "title": "Sitzung 101"}]
        },
        "20102-session.json": {
            "data": [{"dateStart": "2023-04-28T14:00:00+02:00", "title": "Sitzung 102"}]
        },
    }
    conn = _make_connector(sessions)

    handles = conn.discover(since=None)

    assert len(handles) == 2, (
        f"both same-date sessions must be discovered, got handles: {handles}"
    )
    assert len(set(handles)) == 2, "handles must be unique"

    titles = set()
    for handle in handles:
        raw = conn.fetch(handle)
        assert "skip_reason" not in raw, f"handle {handle!r} must be fetchable"
        items = raw["items"]
        assert items, f"handle {handle!r} must carry its session's items"
        titles.add(items[0]["title"])
    assert titles == {"Sitzung 101", "Sitzung 102"}, (
        "each handle must resolve to ITS OWN session's speeches"
    )
