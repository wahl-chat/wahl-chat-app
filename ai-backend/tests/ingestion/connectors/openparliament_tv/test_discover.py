# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for OpenParliamentTvConnector.discover() — WP20+21 enumeration + lookback (D-01/D-08/Q3).

Wave-0 SCAFFOLD: the connector module does not exist yet. The top-level
`pytest.importorskip(...)` makes this whole file SKIP cleanly until the op
connector lands (later wave), at which point the real assertions run.

Covers:
  - test_lookback_realigns: a trailing session file that gains a newly-aligned
    speech BELOW the prior cursor is re-picked because discover() floors at
    `since − LOOKBACK` (Q3 — alignment-backlog re-scan).
"""

from __future__ import annotations

from typing import Any

import pytest

# Wave-0 guard: SKIP until the op connector exists.
connector_mod = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.connector",
    reason="op connector not yet implemented (later wave) — Wave-0 scaffold",
)

OpenParliamentTvConnector = getattr(connector_mod, "OpenParliamentTvConnector")


class _FakeOpClient:
    """Minimal op-bulk client stand-in.

    list_session_files() returns the enumerated `processed/*-session.json`
    external ids (YYYYMMDD ints derived from each session's dateStart); the
    connector floors the scan at `since − LOOKBACK`.
    """

    def __init__(self, session_external_ids: list[int]) -> None:
        self._ids = sorted(session_external_ids)

    def list_session_files(self) -> list[int]:
        return list(self._ids)

    def fetch_session(self, external_id: int) -> Any:  # noqa: ANN401
        return {"meta": {}, "data": []}


def _make_connector(session_external_ids: list[int]) -> Any:  # noqa: ANN401
    """Build an OpenParliamentTvConnector with __init__ bypassed (no network/key)."""
    conn = object.__new__(OpenParliamentTvConnector)
    conn._client = _FakeOpClient(session_external_ids)  # type: ignore[attr-defined]
    return conn


def test_lookback_realigns() -> None:
    """Q3/D-08: discover() re-scans below the prior cursor by the LOOKBACK window.

    Prior op cursor advanced to 20230601 (a later-dated speech aligned first).
    An earlier session dated 20230501 only just aligned — it sits BELOW the
    cursor. With a forward-only floor it would be stranded forever; with the
    `since − LOOKBACK (≥60 days)` floor it is re-picked.
    """
    since = 20230601
    conn = _make_connector([20230501, 20230601, 20230615])

    discovered = conn.discover(since=since)
    discovered = [int(x) for x in discovered]

    assert 20230501 in discovered, (
        "an out-of-order newly-aligned session below the cursor must be re-picked "
        "via the lookback floor (since − LOOKBACK)"
    )
    # The floor still excludes ancient history far outside the lookback window.
    assert all(d >= since - 100000 for d in discovered)


# ---------------------------------------------------------------------------
# (f) Same-date session collision — both sessions must be discovered + fetchable
# ---------------------------------------------------------------------------


class _FakeOpBasenameClient:
    """Op-bulk client stand-in enumerating basename session files."""

    def __init__(self, sessions: dict[str, dict]) -> None:
        self._sessions = sessions

    def list_session_files(self) -> list[str]:
        return list(self._sessions)

    def fetch_session_json(self, name: str) -> dict:
        return self._sessions[name]


def test_same_date_sessions_both_discovered_and_fetchable() -> None:
    """(f) Two sessions whose earliest dateStart falls on the SAME calendar date
    must BOTH appear in discover() output and both be fetchable — previously the
    str(ext) cache key collided and one session's speeches were never ingested."""
    sessions = {
        "20-101-session.json": {
            "data": [{"dateStart": "2023-04-28T09:00:00+02:00", "title": "Sitzung 101"}]
        },
        "20-102-session.json": {
            "data": [{"dateStart": "2023-04-28T14:00:00+02:00", "title": "Sitzung 102"}]
        },
    }
    conn = object.__new__(OpenParliamentTvConnector)
    conn._client = _FakeOpBasenameClient(sessions)  # type: ignore[attr-defined]

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


def test_same_date_direct_ext_fast_path_gets_unique_handles() -> None:
    """(f) The direct-ext fast path disambiguates same-date entries with a
    run-local suffix instead of silently collapsing them."""
    conn = _make_connector([20230428])
    # Simulate a client enumerating the same date twice (two same-day sessions).
    conn._client = _FakeOpClient([20230428, 20230428])  # type: ignore[attr-defined]

    handles = conn.discover(since=None)

    assert len(handles) == 2, "both same-date direct-ext sessions must be discovered"
    assert len(set(handles)) == 2, "handles must be unique (run-local suffix)"
