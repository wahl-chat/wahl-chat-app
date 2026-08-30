# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Asserts this package's constants against corpus-contract.json.

Mirrors ai-backend/tests/test_corpus_contract.py. See AGENTS.md for the other
two guards.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(scope="module")
def contract() -> dict[str, Any]:
    """Raw JSON, not via ingestion.corpus_contract — so a loader bug cannot hide
    by comparing the loader against itself."""
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "corpus-contract.json").read_text(encoding="utf-8"))


# schemas.py enums stay static so mypy and Pydantic keep real member types.


def test_source_type_enum_matches_contract(contract: dict[str, Any]) -> None:
    from ingestion.schemas import SourceType

    assert {e.value for e in SourceType} == set(contract["source_types"])


def test_authority_tier_enum_matches_contract(contract: dict[str, Any]) -> None:
    from ingestion.schemas import AuthorityTier

    assert {e.value for e in AuthorityTier} == set(contract["authority_tiers"])


# Contract-derived modules.


def test_governance_levels_match_contract(contract: dict[str, Any]) -> None:
    from ingestion import governance_levels as levels

    expected = contract["governance_levels"]
    assert levels.FEDERAL == expected["federal"]
    assert levels.STATE == expected["state"]
    assert levels.MUNICIPAL == expected["municipal"]
    assert levels.EU == expected["eu"]
    assert levels.ALL_LEVELS == frozenset(expected["all_levels"])
    assert levels.EU not in levels.ALL_LEVELS


def test_vector_space_matches_contract(contract: dict[str, Any]) -> None:
    """Pairs with the backend's identical assertion — together they stop writer
    and reader drifting into different vector spaces."""
    import os

    if any(
        os.getenv(var)
        for var in ("EMBEDDING_MODEL", "EMBEDDING_DIM", "COLLECTION_NAME")
    ):
        pytest.skip("embedding env overrides set — defaults not observable")

    from ingestion import corpus

    assert corpus.EMBEDDING_MODEL == contract["embedding"]["model"]
    assert corpus.EMBEDDING_DIM == contract["embedding"]["dim"]
    assert corpus.resolve_embedding_provider() == contract["embedding"]["provider"]


def test_collection_name_follows_contract_template(contract: dict[str, Any]) -> None:
    import os

    if os.getenv("COLLECTION_NAME"):
        pytest.skip("COLLECTION_NAME overridden")

    from ingestion import corpus

    assert corpus.COLLECTION_NAME == contract["collection"]["name_template"].format(
        env=corpus.ENV
    )


def test_fingerprint_identity_matches_contract(contract: dict[str, Any]) -> None:
    from ingestion import corpus

    assert corpus.FINGERPRINT_POINT_ID == contract["collection"]["fingerprint_point_id"]
    assert (
        corpus.FINGERPRINT_SOURCE_TYPE
        == contract["collection"]["fingerprint_source_type"]
    )


def test_legislature_periods_match_contract(contract: dict[str, Any]) -> None:
    """Every period, verbatim."""
    from ingestion.legislature_config import LEGISLATURE_CONFIG

    expected = contract["legislature_periods"]
    assert {str(k) for k in LEGISLATURE_CONFIG} == set(expected)
    for period_id, row in expected.items():
        cfg = LEGISLATURE_CONFIG[int(period_id)]
        assert cfg.region == row["region"]
        assert cfg.label == row["label"]
        assert cfg.date_from == row["date_from"]
        assert cfg.date_to == row["date_to"]
        assert cfg.wahlperiode == row["wahlperiode"]


# Wiring guards.


def test_aw_taxonomy_reexports_shared_levels() -> None:
    """Identity, not equality: a re-introduced local frozenset in
    topic_taxonomy_config.py would compare equal but not be the same object."""
    from ingestion import governance_levels as levels
    from ingestion.connectors.abgeordnetenwatch import topic_taxonomy_config as aw

    assert aw.FEDERAL == levels.FEDERAL
    assert aw.STATE == levels.STATE
    assert aw.MUNICIPAL == levels.MUNICIPAL
    assert aw.ALL_LEVELS is levels.ALL_LEVELS


def test_setup_collection_reexports_shared_corpus() -> None:
    """Redefining these would let the write side stamp a fingerprint the read
    side never matches."""
    from ingestion import corpus, setup_collection

    assert setup_collection.COLLECTION_NAME is corpus.COLLECTION_NAME
    assert setup_collection.check_fingerprint is corpus.check_fingerprint
    assert setup_collection.FINGERPRINT_POINT_ID is corpus.FINGERPRINT_POINT_ID


def test_ingestion_does_not_import_the_backend() -> None:
    """Independence runs both ways."""
    root = Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(root)}:{num}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if line.startswith(("from src", "import src"))
    ]
    assert not offenders, f"ingestion must not import the backend: {offenders}"
