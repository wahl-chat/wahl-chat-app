# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Parity guards for duplicated constant surfaces.

- retrieve.py duplicates the schemas enums as Literal types (Python Enum in a
  Gemini tool declaration triggers a langchain-google-genai schema bug, so the
  tool surface uses Literal[...]). Without a parity test, adding a new
  SourceType silently leaves the tool schema stale.
- ingestion/src/ingestion/governance_levels.py hoists the governance-level constants out
  of the abgeordnetenwatch connector; until the connector is re-pointed to
  re-export from the shared module, both definitions must stay identical.
"""

from __future__ import annotations

from typing import get_args

from src.retrieve import AuthorityTierLiteral, SourceTypeLiteral
from ingestion.schemas import AuthorityTier, SourceType


def test_source_type_literal_matches_enum() -> None:
    """SourceTypeLiteral (retrieve.py tool surface) == SourceType enum values."""
    assert set(get_args(SourceTypeLiteral)) == {e.value for e in SourceType}


def test_authority_tier_literal_matches_enum() -> None:
    """AuthorityTierLiteral (retrieve.py tool surface) == AuthorityTier enum values."""
    assert set(get_args(AuthorityTierLiteral)) == {e.value for e in AuthorityTier}


def test_levels_module_matches_aw_taxonomy_definitions() -> None:
    """The AW taxonomy RE-EXPORTS the shared levels module's constants.
    Identity assertions guard against someone re-introducing local definitions
    in topic_taxonomy_config.py (equal-but-distinct objects would fail)."""
    from ingestion import governance_levels as levels
    from ingestion.connectors.abgeordnetenwatch import topic_taxonomy_config as aw

    assert aw.FEDERAL == levels.FEDERAL
    assert aw.STATE == levels.STATE
    assert aw.MUNICIPAL == levels.MUNICIPAL
    # Identity (not equality): a re-introduced local frozenset would be equal
    # but not the SAME object — this is the actual re-export guard.
    assert aw.ALL_LEVELS is levels.ALL_LEVELS


def test_retrieve_imports_levels_from_shared_module() -> None:
    """The framework retrieval module must use the SHARED levels objects, not a
    connector-owned or locally re-defined copy. Asserted by object identity: a
    re-defined ALL_LEVELS (or one sourced from a connector) would be a different
    object and fail here."""
    import ingestion.governance_levels as levels
    import src.retrieve as retrieve_mod

    assert retrieve_mod.ALL_LEVELS is levels.ALL_LEVELS, (
        "retrieve.py must bind ALL_LEVELS from ingestion.governance_levels, not a "
        "connector-owned or locally re-defined copy"
    )
