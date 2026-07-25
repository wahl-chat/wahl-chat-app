# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest fixtures for the openparliament_tv connector test suite.

Provides:
  - session_json_text: raw text of the trimmed op bulk session-JSON fixture
  - session_json:      json.loads(...) of the same fixture (JSON:API shape)

The fixture loads from the local `fixtures/` directory — no I/O guard needed as
it is a committed static file (not network or live-service dependent).

Pattern mirrors tests/ingestion/connectors/bundestag_speeches/conftest.py:
  _FIXTURES_DIR = Path(__file__).parent / "fixtures"

Fixture content (`20101-session.trimmed.json`) — FOUR data[] speech items
spanning every alignment branch:
  (a) ALIGNED + `proceedings` CDU/CSU main speaker (faction.wid="Q1023134"),
      officialTitle "Tagesordnungspunkt 20", EP 20 / session 101, first sentence
      timeStart "1.000" (string, per-speech-relative seconds).
  (b) UNALIGNED item (media.aligned=false, empty textContents).
  (c) ASR-only item (media.aligned=true but textContents[0].type="generated").
  (d) MINISTER item (aligned+proceedings, people[].faction.wid="") to exercise
      the MdB / `unbekannt` fallback.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_SESSION_FIXTURE = _FIXTURES_DIR / "20101-session.trimmed.json"


@pytest.fixture()
def session_json_text() -> str:
    """Return the raw text of the trimmed op bulk session-JSON fixture.

    Used by parser/corpus/discover tests. Static committed file.
    """
    return _SESSION_FIXTURE.read_text(encoding="utf-8")


@pytest.fixture()
def session_json() -> dict[str, Any]:
    """Return the parsed (json.loads) trimmed op bulk session-JSON fixture.

    JSON:API shape `{"meta": {...}, "data": [<4 speech items>]}`.
    """
    return json.loads(_SESSION_FIXTURE.read_text(encoding="utf-8"))
