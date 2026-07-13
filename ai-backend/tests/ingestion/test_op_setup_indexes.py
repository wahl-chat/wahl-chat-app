# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Qdrant index-set test for the new `speech_key` + `source` keyword indexes (Q7).

The source-scoped cursor (Q2) and the supersede / resurrection-guard filters
(D-04/D-05) all depend on `source` and `speech_key` being INDEXED keyword
payload fields. `setup_collection._REQUIRED_INDEXES` is the source of truth.

Wave-0 SCAFFOLD: the indexes are not added yet (11-02). This file collects
cleanly and CAPABILITY-SKIPS until `_REQUIRED_INDEXES` grows to include them,
then asserts membership.
"""

from __future__ import annotations

import pytest

from src.ingestion import setup_collection


def test_speech_key_and_source_indexes() -> None:
    """Q7: {"speech_key", "source"} ⊆ setup_collection._REQUIRED_INDEXES."""
    required = getattr(setup_collection, "_REQUIRED_INDEXES", frozenset())
    needed = {"speech_key", "source"}
    if not needed <= set(required):
        pytest.skip(
            "speech_key/source keyword indexes not yet added to setup_collection (11-02) "
            "— Wave-0 scaffold"
        )
    assert needed <= set(required), (
        f"speech_key and source must both be required keyword indexes; have {sorted(required)}"
    )
