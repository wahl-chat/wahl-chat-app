# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Local mode: seeding the Firestore emulator must need NO cloud credentials.

`make test-local-mode` has always pointed here, but the file never existed and neither
did the guard it describes — the seed script validated ADC whenever no service-account
file was present, so an expired `gcloud auth` login blocked local seeding outright
even though the emulator verifies no credential at all.

The live end-to-end case needs `make stores-up` and skips otherwise, so this module
stays runnable (and honest) without the emulator; the guard itself is asserted purely.
"""

from __future__ import annotations

import importlib.util
import os
import socket
from pathlib import Path

import pytest

_SEED_SCRIPT = (
    Path(__file__).resolve().parents[2] / "firebase" / "scripts" / "seed_firestore.py"
)
_EMULATOR_HOST = os.getenv("FIRESTORE_EMULATOR_HOST", "localhost:8081")
_EMULATOR_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "demo-wahl-chat")


def _load_seed_module(monkeypatch: pytest.MonkeyPatch, **env: str):
    """Import the seed script fresh under a controlled environment.

    It reads ENV/DATA_DIR at import time, so each case needs its own module object.
    """
    for key in ("FIRESTORE_EMULATOR_HOST", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    spec = importlib.util.spec_from_file_location("_seed_under_test", _SEED_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _emulator_reachable() -> bool:
    host, _, port = _EMULATOR_HOST.partition(":")
    try:
        with socket.create_connection((host, int(port or 8081)), timeout=1):
            return True
    except OSError:
        return False


# ===========================================================================
# The guard: emulator mode must not touch ADC
# ===========================================================================


def test_emulator_mode_never_validates_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expired gcloud login must not be able to block local seeding."""
    seed = _load_seed_module(
        monkeypatch,
        FIRESTORE_EMULATOR_HOST=_EMULATOR_HOST,
        GOOGLE_CLOUD_PROJECT=_EMULATOR_PROJECT,
    )

    def _fail(*_a: object, **_k: object) -> None:
        raise AssertionError("emulator mode must not validate cloud credentials")

    monkeypatch.setattr(seed, "_validate_adc", _fail)
    monkeypatch.setattr(seed, "_find_credentials_file", _fail)

    client = seed.initialize_firebase()
    assert client.project == _EMULATOR_PROJECT


def test_emulator_mode_requires_an_explicit_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each project is its own emulator namespace, so inheriting one silently would
    seed data the app never reads."""
    seed = _load_seed_module(monkeypatch, FIRESTORE_EMULATOR_HOST=_EMULATOR_HOST)
    with pytest.raises(SystemExit):
        seed.initialize_firebase()


def test_cloud_mode_still_validates_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard must be scoped to the emulator, not weaken real deploys."""
    seed = _load_seed_module(monkeypatch)
    monkeypatch.setattr(seed, "_find_credentials_file", lambda: None)

    called: list[bool] = []
    monkeypatch.setattr(seed, "_validate_adc", lambda: called.append(True))
    monkeypatch.setattr(seed.firebase_admin, "initialize_app", lambda *a, **k: None)
    monkeypatch.setattr(seed.firestore, "client", lambda *a, **k: object())

    seed.initialize_firebase()
    assert called == [True], "ADC validation must still run without the emulator"


# ===========================================================================
# Live: seeding a running emulator, credentials or not
# ===========================================================================


@pytest.mark.skipif(
    not _emulator_reachable(),
    reason=f"needs the Firestore emulator at {_EMULATOR_HOST} (run `make stores-up`)",
)
def test_seeding_the_live_emulator_needs_no_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = _load_seed_module(
        monkeypatch,
        FIRESTORE_EMULATOR_HOST=_EMULATOR_HOST,
        GOOGLE_CLOUD_PROJECT=_EMULATOR_PROJECT,
    )
    db = seed.initialize_firebase()

    context_ids = seed.seed_contexts(db)
    assert context_ids, "the dev fixtures must contain at least one context"

    # Every context file on disk reached the emulator.
    stored = {doc.id for doc in db.collection("contexts").stream()}
    assert set(context_ids) <= stored
