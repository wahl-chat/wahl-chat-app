# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared governance-level constants — framework-owned, connector-independent.

These values MUST match ``Context.level`` values exactly ("federal" | "state" |
"municipal"; "eu" is reserved for future EU election contexts). They live here,
not inside a connector, so the standalone retrieval module never imports a
connector (which would invert the framework→connector layering). Connectors
may keep identical definitions — a parity test pins the equality.

``ALL_LEVELS`` is the {federal, state, municipal} relevance fallback used when
a vote's topic cannot be classified — ``EU`` is deliberately NOT part of it
(AW carries no EU parliament data; adding it would change down-rank behavior).
"""

from __future__ import annotations

from typing import FrozenSet

FEDERAL: str = "federal"
STATE: str = "state"
MUNICIPAL: str = "municipal"
# Reserved for future EU election contexts (European Parliament). NOT included
# in ALL_LEVELS — see module docstring.
EU: str = "eu"

ALL_LEVELS: FrozenSet[str] = frozenset({FEDERAL, STATE, MUNICIPAL})
