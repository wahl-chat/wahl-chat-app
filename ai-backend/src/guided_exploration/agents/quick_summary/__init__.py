# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Quick-summary streaming agent for guided exploration."""

from src.guided_exploration.agents.quick_summary.implementation import (
    QuickSummaryAgent,
)
from src.guided_exploration.agents.quick_summary.interface import (
    QuickSummaryInput,
    QuickSummaryOutput,
)

__all__ = [
    "QuickSummaryAgent",
    "QuickSummaryInput",
    "QuickSummaryOutput",
]
