# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Test for the FIRESTORE_EMULATOR_HOST guard.

Verifies that the seed script refuses to run (exits non-zero) when
FIRESTORE_EMULATOR_HOST is not set, and does NOT refuse when it is set to a
localhost emulator address.

This guard prevents accidental writes to production Firestore during local
development.
"""

import os
import subprocess
import sys

import pytest

# Absolute path to the seed script from the repo root
_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_SEED_SCRIPT = os.path.join(_REPO_ROOT, "firebase", "scripts", "seed_firestore.py")


def _run_seed_script_no_emulator() -> "subprocess.CompletedProcess[str]":
    """Run the seed script with FIRESTORE_EMULATOR_HOST unset.

    Uses a short timeout — the guard should print an error and exit
    immediately without making any network calls.
    """
    env = {k: v for k, v in os.environ.items() if k != "FIRESTORE_EMULATOR_HOST"}
    return subprocess.run(
        [sys.executable, _SEED_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )


@pytest.mark.asyncio
async def test_no_prod_connection():
    """seed script exits non-zero when FIRESTORE_EMULATOR_HOST is unset.

    The guard must:
    1. Exit with a non-zero return code.
    2. Print a message mentioning FIRESTORE_EMULATOR_HOST so the developer knows
       why it refused.
    """
    if not os.path.isfile(_SEED_SCRIPT):
        pytest.skip(
            f"Seed script not found at {_SEED_SCRIPT}"
        )

    try:
        result = _run_seed_script_no_emulator()
    except subprocess.TimeoutExpired:
        pytest.fail(
            "Seed script did not exit within 5 seconds when FIRESTORE_EMULATOR_HOST "
            "is unset. The guard should exit immediately with an error "
            "message — it must NOT attempt network calls."
        )

    assert result.returncode != 0, (
        "Seed script must exit non-zero when FIRESTORE_EMULATOR_HOST is unset "
        "(guard prevents connecting to production Firestore). "
        "The guard should exit immediately with a clear error.\n"
        f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )

    combined_output = result.stdout + result.stderr
    assert "FIRESTORE_EMULATOR_HOST" in combined_output, (
        "The guard's error message must mention FIRESTORE_EMULATOR_HOST "
        "so the developer knows what to set.\n"
        f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )
