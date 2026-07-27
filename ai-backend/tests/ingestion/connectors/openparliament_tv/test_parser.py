# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for openparliament_tv.parser (aligned+proceedings gate).

The module-under-test does not exist yet. The top-level
`pytest.importorskip(...)` makes this whole file SKIP cleanly until the parser
lands, at which point the real assertions run.

Covers:
  - test_skip_unaligned_and_asr: parser yields a usable speech ONLY for
    aligned+proceedings items; unaligned (media.aligned=false) and ASR-only
    (textContents[0].type=="generated") items are marked skippable / dropped.
"""

from __future__ import annotations

import pytest

# SKIP until src.ingestion.connectors.openparliament_tv.parser exists.
parser = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.parser",
    reason="op parser not yet implemented",
)


def _aligned_proceedings_media_ids(parsed: list[dict]) -> set[str]:
    """Collect origin media IDs from parsed speech dicts, tolerant of key names."""
    ids: set[str] = set()
    for sp in parsed:
        media = sp.get("media") or sp.get("item", {}).get("media") or {}
        mid = media.get("originMediaID") or sp.get("origin_media_id")
        if mid:
            ids.add(str(mid))
    return ids


def test_skip_unaligned_and_asr(session_json: dict) -> None:
    """only aligned+proceedings speeches survive; unaligned + ASR-only are skipped.

    The trimmed fixture has 4 items:
      - originMediaID 7553315: aligned + proceedings  → KEEP
      - originMediaID 7553320: media.aligned=false     → SKIP (not aligned yet)
      - originMediaID 7553330: aligned + generated-only → SKIP (no proceedings)
      - originMediaID 7553340: aligned + proceedings    → KEEP (minister)
    The parser (or the normalize gate it feeds) must yield usable speech records
    for exactly the two aligned+proceedings items and never for the other two.
    """
    parse = getattr(parser, "parse_session_json", None) or getattr(
        parser, "parse_speeches_from_session"
    )
    parsed = parse(session_json)
    assert isinstance(parsed, list)

    kept = _aligned_proceedings_media_ids(parsed)
    # Both aligned+proceedings speeches are kept ...
    assert "7553315" in kept
    assert "7553340" in kept
    # ... and neither the unaligned nor the ASR-only speech is kept.
    assert "7553320" not in kept, "unaligned speech must be skipped"
    assert "7553330" not in kept, "ASR-only (generated) speech must be skipped"
    assert len(kept) == 2
