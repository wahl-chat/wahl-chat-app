# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Main-chat follow-up chip generator (3 fixed-slot quick replies)."""

from src.guided_exploration.agents.main_chat_followup_generator.implementation import (
    MainChatFollowUpGenerator,
)
from src.guided_exploration.agents.main_chat_followup_generator.interface import (
    MainChatFollowUpInput,
    MainChatFollowUpResult,
)

__all__ = [
    "MainChatFollowUpGenerator",
    "MainChatFollowUpInput",
    "MainChatFollowUpResult",
]
