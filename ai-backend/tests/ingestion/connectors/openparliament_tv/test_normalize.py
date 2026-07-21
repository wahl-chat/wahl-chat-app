# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for OpenParliamentTvConnector.normalize() — the skip-and-warn contract:
a skip_reason payload and a zero-usable-speech session must both raise
ValueError so run_connector skip-and-continues without advancing the cursor.
"""

from __future__ import annotations

import pytest

connector_mod = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.connector",
    reason="op connector not yet implemented",
)

OpenParliamentTvConnector = getattr(connector_mod, "OpenParliamentTvConnector")


def _make_connector():
    return object.__new__(OpenParliamentTvConnector)


def test_normalize_raises_on_skip_reason() -> None:
    """A fetch() skip_reason dict converts to an immediate ValueError."""
    conn = _make_connector()
    with pytest.raises(ValueError, match="not in discover cache"):
        conn.normalize({"skip_reason": "op session 20101 not in discover cache"})


def test_normalize_raises_on_zero_usable_speeches() -> None:
    """A session whose items are all unaligned / ASR-only / empty (alignment gate)
    yields zero ChunkRecords → ValueError so the cursor does NOT advance past
    the un-aligned session."""
    conn = _make_connector()
    raw = {
        "external_id": "20101-session.json",
        "items": [
            # Unaligned item — the alignment gate drops it inside build_chunk_records.
            {"media": {"aligned": False}, "textContents": []},
            # Aligned but ASR-only (no proceedings transcript).
            {
                "media": {"aligned": True},
                "textContents": [{"type": "generated", "textBody": []}],
            },
        ],
        "mdb_lookup": None,
    }
    with pytest.raises(ValueError, match="zero usable"):
        conn.normalize(raw)


def test_normalize_raises_on_empty_item_list() -> None:
    """An empty session (no items at all) is also a zero-usable ValueError."""
    conn = _make_connector()
    with pytest.raises(ValueError, match="zero usable"):
        conn.normalize({"external_id": "20102-session.json", "items": [], "mdb_lookup": None})
