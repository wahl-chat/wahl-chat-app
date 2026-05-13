# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Study-context position lookup for the chip generator.

The main-chat chip generator needs the full position landscape for the
current topic — not just the per-query RAG retrieval — so it can pick
slot-1 follow-ups that point at aspects the user has *not* yet seen.
This module loads the per-party position JSON shipped under
``data/study-fake-parties/positions/`` and renders all positions for a
single topic, grouped by party and subtopic.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.guided_exploration.services.study_context import (
    STUDY_PARTIES,
    STUDY_PARTY_IDS,
    get_study_topic,
    is_study_context,
)

_POSITIONS_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "study-fake-parties"
    / "positions"
)
_positions_cache: dict[str, list[dict]] = {}


def _load_party_positions(party_id: str) -> list[dict]:
    cached = _positions_cache.get(party_id)
    if cached is not None:
        return cached
    path = _POSITIONS_DIR / f"{party_id}.json"
    if not path.exists():
        _positions_cache[party_id] = []
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    _positions_cache[party_id] = data
    return data


def format_topic_positions_for_chips(context_id: str) -> str:
    """Return all positions for a study topic, grouped by party.

    Empty string for non-study contexts — the chip generator falls back
    to its existing per-query ``available_context`` then.
    """
    if not is_study_context(context_id):
        return ""

    topic = get_study_topic(context_id)
    blocks: list[str] = []
    for party_id in STUDY_PARTY_IDS:
        positions = [
            p for p in _load_party_positions(party_id) if p.get("topic") == topic
        ]
        if not positions:
            continue
        party_name = STUDY_PARTIES[party_id].name
        by_subtopic: dict[str, list[dict]] = {}
        for p in positions:
            by_subtopic.setdefault(p.get("subtopic", ""), []).append(p)

        lines = [f"### {party_name}"]
        for subtopic, items in by_subtopic.items():
            label = subtopic if subtopic else "(ohne Subtopic)"
            lines.append(f"**{label}**")
            for it in items:
                claim = (it.get("claim") or "").strip()
                cid = it.get("id", "")
                if claim:
                    lines.append(f"- [{cid}] {claim}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
