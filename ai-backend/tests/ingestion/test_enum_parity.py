# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Parity guards for duplicated constant surfaces (B7 / B10).

- retrieve.py duplicates the schemas enums as Literal types (clean Gemini
  tool-schema generation, issue #409). Without a parity test, adding a new
  SourceType silently leaves the tool schema stale.
- src/ingestion/levels.py hoists the governance-level constants out of the
  abgeordnetenwatch connector (B7); until the connector is re-pointed to
  re-export from the shared module, both definitions must stay identical.
"""

from __future__ import annotations

from typing import get_args

from src.ingestion.retrieve import AuthorityTierLiteral, SourceTypeLiteral
from src.ingestion.schemas import AuthorityTier, SourceType


def test_source_type_literal_matches_enum() -> None:
    """B10: SourceTypeLiteral (retrieve.py tool surface) == SourceType enum values."""
    assert set(get_args(SourceTypeLiteral)) == {e.value for e in SourceType}


def test_authority_tier_literal_matches_enum() -> None:
    """B10: AuthorityTierLiteral (retrieve.py tool surface) == AuthorityTier enum values."""
    assert set(get_args(AuthorityTierLiteral)) == {e.value for e in AuthorityTier}


def test_levels_module_matches_aw_taxonomy_definitions() -> None:
    """B7: the AW taxonomy RE-EXPORTS the shared levels module's constants.
    Identity assertions guard against someone re-introducing local definitions
    in topic_taxonomy_config.py (equal-but-distinct objects would fail)."""
    from src.ingestion import levels
    from src.ingestion.connectors.abgeordnetenwatch import topic_taxonomy_config as aw

    assert aw.FEDERAL == levels.FEDERAL
    assert aw.STATE == levels.STATE
    assert aw.MUNICIPAL == levels.MUNICIPAL
    # Identity (not equality): a re-introduced local frozenset would be equal
    # but not the SAME object — this is the actual re-export guard.
    assert aw.ALL_LEVELS is levels.ALL_LEVELS


def test_retrieve_imports_levels_from_shared_module() -> None:
    """B7: the framework retrieval module must not import a connector for levels."""
    import inspect

    import src.ingestion.retrieve as retrieve_mod

    src_text = inspect.getsource(retrieve_mod)
    assert "from src.ingestion.levels import" in src_text
    assert "abgeordnetenwatch.topic_taxonomy_config" not in src_text, (
        "retrieve.py (framework) must not import connector-owned modules"
    )
