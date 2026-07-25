# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Shared governance-level constants — framework-owned, connector-independent.

These values MUST match ``Context.level`` values exactly ("federal" | "state" |
"municipal"; "eu" is reserved for future EU election contexts). They live here,
not inside the abgeordnetenwatch connector's ``topic_taxonomy_config``, so the
STANDALONE retrieval module need not import a connector (which would invert the
framework→connector layering). The framework (``retrieve.py``) imports from
here; connectors may re-export from this module (the abgeordnetenwatch taxonomy
keeps its own identical definitions — a parity test pins the equality).

Semantics copied EXACTLY from
``connectors/abgeordnetenwatch/topic_taxonomy_config.py``:
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
