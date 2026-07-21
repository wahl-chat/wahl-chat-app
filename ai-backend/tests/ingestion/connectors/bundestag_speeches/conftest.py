# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest fixtures for the bundestag_speeches connector test suite.

Provides:
  - protocol_xml: text content of the trimmed plenary protocol XML fixture
  - mdb_xml_path: Path to the tiny MdB-Stammdaten XML fixture

The fixtures load from the local `fixtures/` directory — no I/O guard
needed as they are committed static files (not network or live-service
dependent).

Pattern mirrors tests/ingestion/connectors/abgeordnetenwatch/conftest.py:
  _FIXTURES_DIR = Path(__file__).parent / "fixtures"
"""

from __future__ import annotations

from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Protocol XML fixture loader
# ---------------------------------------------------------------------------


@pytest.fixture()
def protocol_xml() -> str:
    """Return the text content of the trimmed plenary protocol XML fixture.

    The fixture contains:
      - Two main <rede> nodes: one SPD speaker, one BÜNDNIS 90/DIE GRÜNEN merged-name
      - One <rede> with a speaker ID starting with "999" (non-MdB, droppable)
      - A <kommentar> node inside a speech body (must be skipped by the parser)

    Used by: test_parser.py.
    """
    return (_FIXTURES_DIR / "protocol_sample.xml").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# MdB Stammdaten XML path fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def mdb_xml_path() -> Path:
    """Return the Path to the tiny MdB-Stammdaten XML fixture.

    The fixture contains 3 MDB records:
      - ID 11004870 (SPD): party resolved via PARTEI_KURZ
      - ID 11004220 (BÜNDNIS 90/DIE GRÜNEN): party resolved via PARTEI_KURZ
      - ID 11003444 (CDU/CSU): PARTEI_KURZ is empty; party only resolves via
        WAHLPERIODEN INSTITUTION with INSART_LANG="Fraktion/Gruppe" and WP=21

    Used by: test_mdb.py.
    """
    return _FIXTURES_DIR / "mdb_sample.xml"
