# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared pytest fixtures for the Abgeordnetenwatch connector test suite.

Provides:
  - aw_poll_3602_poll: the poll metadata fixture (poll 3602 from the AW API)
  - aw_poll_3602_votes: the 710-vote fixture including the Req 6 empty-fraction edge case
  - emulator_db: Firestore emulator handle (skipped if emulator not reachable)

The golden fixtures (aw_poll_3602_poll.json, aw_poll_3602_votes.json) contain
data verified from the live AW API (poll 3602 "Corona-Maßnahmen zum Schutz der
Bevölkerung", parliament period 111, date 2020-05-14).

The emulator_db fixture mirrors the emulator-guard pattern used across the
ingestion connector tests using a socket-reachability check instead of a
mere env-var-presence guard.
"""

from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any

import pytest

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Golden fixture loaders (no I/O guard needed — pure JSON reads)
# ---------------------------------------------------------------------------


@pytest.fixture()
def aw_poll_3602_poll() -> dict:
    """Load the aw_poll_3602_poll.json golden fixture.

    Shape: single poll item (data: {...}) for poll id=3602.
    Used by: test_stance.py golden-record assertion (Req 10).
    """
    return json.loads((_FIXTURES_DIR / "aw_poll_3602_poll.json").read_text())


@pytest.fixture()
def aw_poll_3602_votes() -> dict:
    """Load the aw_poll_3602_votes.json golden fixture.

    Shape: 710 per-mandate vote items (data: [...]) including one vote
    with fraction=[] to exercise the Req 6 degenerate-input guard.
    Used by: test_stance.py golden-record assertion (Req 10).
    """
    return json.loads((_FIXTURES_DIR / "aw_poll_3602_votes.json").read_text())


# ---------------------------------------------------------------------------
# Firestore emulator fixture (socket-reachability guard — mirrors the
# emulator-guard pattern used across the ingestion connector tests)
# ---------------------------------------------------------------------------


def _emulator_reachable() -> bool:
    """Return True if the Firestore emulator port is accepting connections."""
    _host_env = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
    if not _host_env:
        return False
    if ":" in _host_env:
        _host, _port_str = _host_env.rsplit(":", 1)
        _port = int(_port_str)
    else:
        _host = _host_env or "localhost"
        _port = 8081
    try:
        with socket.create_connection((_host, _port), timeout=2):
            return True
    except OSError:
        return False


@pytest.fixture()
def emulator_db() -> Any:
    """Yield a Firestore client connected to the local emulator.

    Skips automatically when the emulator is not reachable so that CI
    (which does not run the emulator) does not fail on this fixture.
    Use only for tests that need real Firestore write/read round-trips.

    Pure-logic tests (test_stance.py) do NOT use this fixture.
    """
    if not _emulator_reachable():
        pytest.skip(
            "Firestore emulator not reachable — run `make stores-up` to start it "
            "(firebase emulators:start --only firestore on port 8081)"
        )

    import firebase_admin
    from firebase_admin import credentials, firestore
    import google.auth.credentials

    class _EmulatorCredentials(credentials.Base):
        def get_credential(self) -> Any:
            return google.auth.credentials.AnonymousCredentials()

    project_id = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
        or "demo-wahl-chat"
    )
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(
            _EmulatorCredentials(), options={"projectId": project_id}
        )

    return firestore.client()
