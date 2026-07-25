# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest fixtures for the Abgeordnetenwatch connector test suite.

Provides:
  - aw_poll_3602_poll: the poll metadata fixture (poll 3602 from the AW API)
  - aw_poll_3602_votes: the 710-vote fixture including the empty-fraction edge case

The golden fixtures (aw_poll_3602_poll.json, aw_poll_3602_votes.json) contain
data verified from the live AW API (poll 3602 "Corona-Maßnahmen zum Schutz der
Bevölkerung", parliament period 111, date 2020-05-14).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Golden fixture loaders (no I/O guard needed — pure JSON reads)
# ---------------------------------------------------------------------------


@pytest.fixture()
def aw_poll_3602_poll() -> dict:
    """Load the aw_poll_3602_poll.json golden fixture.

    Shape: single poll item (data: {...}) for poll id=3602.
    Used by: test_stance.py golden-record assertion.
    """
    return json.loads((_FIXTURES_DIR / "aw_poll_3602_poll.json").read_text())


@pytest.fixture()
def aw_poll_3602_votes() -> dict:
    """Load the aw_poll_3602_votes.json golden fixture.

    Shape: 710 per-mandate vote items (data: [...]) including one vote
    with fraction=[] to exercise the degenerate-input guard.
    Used by: test_stance.py golden-record assertion.
    """
    return json.loads((_FIXTURES_DIR / "aw_poll_3602_votes.json").read_text())
