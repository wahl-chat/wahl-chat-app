# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Guards on this package's use of the shared wahlchat_common contract."""

from __future__ import annotations

from pathlib import Path


def test_schemas_reexports_shared_enums() -> None:
    """Connectors import the enums from ingestion.schemas; those must BE the
    shared ones, or chunks would be stamped with values retrieval never filters
    on."""
    from wahlchat_common.enums import AuthorityTier, SourceType

    from ingestion import schemas

    assert schemas.SourceType is SourceType
    assert schemas.AuthorityTier is AuthorityTier


def test_aw_taxonomy_reexports_shared_levels() -> None:
    """Identity, not equality: a re-introduced local frozenset in
    topic_taxonomy_config.py would compare equal but not be the same object."""
    import wahlchat_common.governance_levels as levels

    from ingestion.connectors.abgeordnetenwatch import topic_taxonomy_config as aw

    assert aw.FEDERAL == levels.FEDERAL
    assert aw.ALL_LEVELS is levels.ALL_LEVELS


def test_setup_collection_reexports_shared_corpus() -> None:
    """Redefining these would let the write side stamp a fingerprint the read
    side never matches."""
    from wahlchat_common import corpus

    from ingestion import setup_collection

    assert setup_collection.COLLECTION_NAME is corpus.COLLECTION_NAME
    assert setup_collection.check_fingerprint is corpus.check_fingerprint


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
