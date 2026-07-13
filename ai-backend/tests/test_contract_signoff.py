# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Regression test: SC6 sign-off section survives CONTRACT.md regeneration.

Ensures that scripts/generate_contract.py writes a correct "## SC6 Review
Sign-off" section (status APPROVED, reviewer, date) into CONTRACT.md so
that a future destructive change fails loudly instead of silently erasing
the human approval record.
"""

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).parent.parent.parent
CONTRACT_PATH = REPO_ROOT / "CONTRACT.md"
SIGNOFF_JSON = REPO_ROOT / "scripts" / "contract_signoff.json"
GENERATOR = REPO_ROOT / "scripts" / "generate_contract.py"
AI_BACKEND = REPO_ROOT / "ai-backend"


@pytest.fixture(scope="module")
def regenerated_contract(tmp_path_factory) -> str:
    """Run the generator in a subprocess and return the contents of CONTRACT.md."""
    result = subprocess.run(
        [sys.executable, str(GENERATOR)],
        cwd=str(AI_BACKEND),
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(AI_BACKEND / "src"),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"generate_contract.py exited with code {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    return CONTRACT_PATH.read_text(encoding="utf-8")


def test_sc6_section_present(regenerated_contract: str) -> None:
    """SC6 regression: the '## SC6 Review Sign-off' heading must exist after regeneration."""
    assert "## SC6 Review Sign-off" in regenerated_contract, (
        "generate_contract.py erased the SC6 Review Sign-off section. "
        "Ensure scripts/contract_signoff.json exists with status=APPROVED."
    )


def test_sc6_status_approved(regenerated_contract: str) -> None:
    """SC6 regression: status must be APPROVED (not PENDING) after regeneration."""
    assert "**Status:** APPROVED" in regenerated_contract, (
        "SC6 Review Sign-off status is not APPROVED in the regenerated CONTRACT.md. "
        "Check scripts/contract_signoff.json."
    )


def test_sc6_reviewer_present(regenerated_contract: str) -> None:
    """SC6 regression: reviewer name must appear in the sign-off section."""
    assert "**Reviewer:** Annika Siefke" in regenerated_contract, (
        "SC6 Review Sign-off is missing the reviewer name. "
        "Check scripts/contract_signoff.json."
    )


def test_sc6_date_present(regenerated_contract: str) -> None:
    """SC6 regression: review date must appear in the sign-off section."""
    assert "**Date:** 2026-06-07" in regenerated_contract, (
        "SC6 Review Sign-off is missing the review date. "
        "Check scripts/contract_signoff.json."
    )


def test_sc6_unblocked_line(regenerated_contract: str) -> None:
    """SC6 regression: the 'unblocked' conclusion must appear in the sign-off."""
    assert "Phase 3 connector work is **unblocked**" in regenerated_contract, (
        "SC6 Review Sign-off is missing the 'unblocked' conclusion line. "
        "Check scripts/contract_signoff.json."
    )


def test_signoff_json_exists() -> None:
    """SC6 regression: scripts/contract_signoff.json must exist and be valid JSON."""
    import json

    assert SIGNOFF_JSON.exists(), (
        f"scripts/contract_signoff.json not found at {SIGNOFF_JSON}. "
        "This file is the source of truth for the SC6 sign-off."
    )
    data = json.loads(SIGNOFF_JSON.read_text(encoding="utf-8"))
    assert data.get("status") == "APPROVED", (
        f"contract_signoff.json status must be 'APPROVED', got {data.get('status')!r}."
    )


def test_deterministic_regeneration() -> None:
    """SC6 regression: running the generator twice yields an empty diff."""
    import os

    env = {**os.environ, "PYTHONPATH": str(AI_BACKEND / "src")}

    subprocess.run(
        [sys.executable, str(GENERATOR)],
        cwd=str(AI_BACKEND),
        env=env,
        check=True,
        capture_output=True,
    )
    first_run = CONTRACT_PATH.read_text(encoding="utf-8")

    subprocess.run(
        [sys.executable, str(GENERATOR)],
        cwd=str(AI_BACKEND),
        env=env,
        check=True,
        capture_output=True,
    )
    second_run = CONTRACT_PATH.read_text(encoding="utf-8")

    assert first_run == second_run, (
        "generate_contract.py is not deterministic: two consecutive runs produced "
        "different CONTRACT.md output. The SC6 sign-off section (or another section) "
        "contains non-deterministic content."
    )
