# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

# GENERATED-PAIR — duplicated in ai-backend/src/ and ingestion/src/ingestion/.
# Edit both; scripts/check_contract_parity.py enforces it.

"""Governance levels. Values must match ``Context.level`` exactly."""

from __future__ import annotations

from typing import FrozenSet

from src.corpus_contract import section

_LEVELS = section("governance_levels")

FEDERAL: str = _LEVELS["federal"]
STATE: str = _LEVELS["state"]
MUNICIPAL: str = _LEVELS["municipal"]
EU: str = _LEVELS["eu"]

# Relevance fallback for unclassifiable votes. EU is excluded on purpose — AW has
# no EU parliament data, and adding it would change down-rank behaviour.
ALL_LEVELS: FrozenSet[str] = frozenset(_LEVELS["all_levels"])
