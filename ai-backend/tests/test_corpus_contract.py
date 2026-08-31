# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Guards on this package's use of the shared wahlchat_corpus contract."""

from __future__ import annotations

from pathlib import Path
from typing import get_args


def test_source_type_literal_matches_enum() -> None:
    """retrieve.py mirrors the enum as a Literal — a Python Enum in a Gemini tool
    declaration trips a langchain-google-genai bug — so the two must be pinned."""
    from wahlchat_corpus.enums import SourceType

    from src.retrieve import SourceTypeLiteral

    assert set(get_args(SourceTypeLiteral)) == {e.value for e in SourceType}


def test_authority_tier_literal_matches_enum() -> None:
    from wahlchat_corpus.enums import AuthorityTier

    from src.retrieve import AuthorityTierLiteral

    assert set(get_args(AuthorityTierLiteral)) == {e.value for e in AuthorityTier}


def test_retrieve_binds_shared_levels() -> None:
    """Identity, not equality: a locally re-defined frozenset would compare equal
    but not be the same object."""
    import wahlchat_corpus.governance_levels as levels

    import src.retrieve as retrieve_mod

    assert retrieve_mod.ALL_LEVELS is levels.ALL_LEVELS


def test_backend_does_not_import_ingestion() -> None:
    """The two deployables share wahlchat_corpus, never each other — an ingestion
    import would drag its connector tree into the chat image."""
    root = Path(__file__).resolve().parents[1]
    offenders = [
        f"{path.relative_to(root)}:{num}"
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
        for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if line.startswith(("from ingestion", "import ingestion"))
    ]
    assert not offenders, f"ai-backend must not import ingestion: {offenders}"
