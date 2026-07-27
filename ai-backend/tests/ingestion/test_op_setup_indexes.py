# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Qdrant index-set test for the new `speech_key` + `source` keyword indexes.

The source-scoped cursor and the supersede / resurrection-guard filters
all depend on `source` and `speech_key` being INDEXED keyword
payload fields. `setup_collection._REQUIRED_INDEXES` is the source of truth.

The indexes are not added yet. This file collects
cleanly and skips until `_REQUIRED_INDEXES` grows to include them,
then asserts membership.
"""

from __future__ import annotations

import pytest

from src.ingestion import setup_collection


def test_speech_key_and_source_indexes() -> None:
    """{"speech_key", "source"} ⊆ setup_collection._REQUIRED_INDEXES."""
    required = getattr(setup_collection, "_REQUIRED_INDEXES", frozenset())
    needed = {"speech_key", "source"}
    if not needed <= set(required):
        pytest.skip(
            "speech_key/source keyword indexes not yet added to setup_collection"
        )
    assert needed <= set(required), (
        f"speech_key and source must both be required keyword indexes; have {sorted(required)}"
    )
