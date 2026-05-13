# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared prompt fragments reused across user-facing agents.

The shared exploration goal (:data:`EXPLORATION_GOALS`) and each
surface's application-context block live in :mod:`.goals`. The citation
directive (:data:`CITATION_DIRECTIVE`) lives in :mod:`.citation` and is
reused verbatim by every agent that emits cited answer text so the
study's ``encountered_positions`` metric stays comparable across
surfaces. The shared behavioural guardrails (:data:`BASE_RULES`) live in
:mod:`.guidelines` and are injected by every user-facing agent so the
neutrality, transparency, limits, privacy, and language policy is
identical across surfaces.
"""

from src.guided_exploration.agents._shared.citation import CITATION_DIRECTIVE
from src.guided_exploration.agents._shared.goals import (
    BASELINE_APPLICATION_CONTEXT_CAPPED,
    BASELINE_APPLICATION_CONTEXT_UNCAPPED,
    EXPLORATION_GOALS,
    LEAF_CHAT_APPLICATION_CONTEXT,
    LEAF_CONTENT_APPLICATION_CONTEXT,
    MAIN_CHAT_FOLLOWUP_APPLICATION_CONTEXT,
    QUICK_SUMMARY_APPLICATION_CONTEXT,
)
from src.guided_exploration.agents._shared.guidelines import BASE_RULES

__all__ = [
    "BASE_RULES",
    "BASELINE_APPLICATION_CONTEXT_CAPPED",
    "BASELINE_APPLICATION_CONTEXT_UNCAPPED",
    "CITATION_DIRECTIVE",
    "EXPLORATION_GOALS",
    "LEAF_CHAT_APPLICATION_CONTEXT",
    "LEAF_CONTENT_APPLICATION_CONTEXT",
    "MAIN_CHAT_FOLLOWUP_APPLICATION_CONTEXT",
    "QUICK_SUMMARY_APPLICATION_CONTEXT",
]
