# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Asserts this package's constants against corpus-contract.json.

The ingestion suite mirrors this file, so both passing means both packages agree
without either importing the other. See AGENTS.md for the other two guards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    """Raw JSON, not via src.corpus_contract — so a loader bug cannot hide by
    comparing the loader against itself."""
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "corpus-contract.json").read_text(encoding="utf-8"))


# retrieve.py's Literals cannot be contract-derived: a Python Enum in a Gemini
# tool declaration hits a langchain-google-genai bug. Hence a test.


def test_source_type_literal_matches_contract(contract: dict[str, Any]) -> None:
    """retrieve.py's SourceTypeLiteral == the contract's source_types."""
    from src.retrieve import SourceTypeLiteral

    assert set(get_args(SourceTypeLiteral)) == set(contract["source_types"])


def test_authority_tier_literal_matches_contract(contract: dict[str, Any]) -> None:
    """retrieve.py's AuthorityTierLiteral == the contract's authority_tiers."""
    from src.retrieve import AuthorityTierLiteral

    assert set(get_args(AuthorityTierLiteral)) == set(contract["authority_tiers"])


# Contract-derived: a failure here means the reading code is wrong, not that
# someone forgot to sync.


def test_governance_levels_match_contract(contract: dict[str, Any]) -> None:
    from src import governance_levels as levels

    expected = contract["governance_levels"]
    assert levels.FEDERAL == expected["federal"]
    assert levels.STATE == expected["state"]
    assert levels.MUNICIPAL == expected["municipal"]
    assert levels.EU == expected["eu"]
    assert levels.ALL_LEVELS == frozenset(expected["all_levels"])
    assert levels.EU not in levels.ALL_LEVELS  # would change vote down-ranking


def test_vector_space_matches_contract(contract: dict[str, Any]) -> None:
    """Asserts the built-in default only (env overrides it) — that default is
    what must not drift between the two packages."""
    import os

    if any(
        os.getenv(var)
        for var in ("EMBEDDING_MODEL", "EMBEDDING_DIM", "COLLECTION_NAME")
    ):
        pytest.skip("embedding env overrides set — defaults not observable")

    from src import corpus

    assert corpus.EMBEDDING_MODEL == contract["embedding"]["model"]
    assert corpus.EMBEDDING_DIM == contract["embedding"]["dim"]
    assert corpus.resolve_embedding_provider() == contract["embedding"]["provider"]


def test_collection_name_follows_contract_template(contract: dict[str, Any]) -> None:
    import os

    if os.getenv("COLLECTION_NAME"):
        pytest.skip("COLLECTION_NAME overridden")

    from src import corpus

    assert corpus.COLLECTION_NAME == contract["collection"]["name_template"].format(
        env=corpus.ENV
    )


def test_fingerprint_identity_matches_contract(contract: dict[str, Any]) -> None:
    """Mismatched ids would mean writing and reading fingerprints at different
    points, so a real mismatch would never be detected."""
    from src import corpus

    assert corpus.FINGERPRINT_POINT_ID == contract["collection"]["fingerprint_point_id"]
    assert (
        corpus.FINGERPRINT_SOURCE_TYPE
        == contract["collection"]["fingerprint_source_type"]
    )


def test_legislature_periods_match_contract(contract: dict[str, Any]) -> None:
    """Every period, verbatim. Drift here silently mis-filters retrieval dates."""
    from src.legislature_config import LEGISLATURE_CONFIG

    expected = contract["legislature_periods"]
    assert {str(k) for k in LEGISLATURE_CONFIG} == set(expected)
    for period_id, row in expected.items():
        cfg = LEGISLATURE_CONFIG[int(period_id)]
        assert cfg.region == row["region"]
        assert cfg.label == row["label"]
        assert cfg.date_from == row["date_from"]
        assert cfg.date_to == row["date_to"]
        assert cfg.wahlperiode == row["wahlperiode"]


# Wiring guards — that this package actually USES the shared definitions.


def test_retrieve_binds_shared_levels() -> None:
    """Identity, not equality: a locally re-defined frozenset would compare
    equal but not be the same object."""
    import src.governance_levels as levels
    import src.retrieve as retrieve_mod

    assert retrieve_mod.ALL_LEVELS is levels.ALL_LEVELS


def test_backend_does_not_import_ingestion() -> None:
    """A stray ingestion import would drag its dependency tree back into the
    chat image."""
    root = Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(root)}:{num}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if line.startswith(("from ingestion", "import ingestion"))
    ]
    assert not offenders, f"ai-backend must not import ingestion: {offenders}"
