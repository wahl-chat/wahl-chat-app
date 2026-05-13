# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Enums for query and message classification in guided exploration."""

from enum import Enum


class QueryType(str, Enum):
    """Type of user query for initial classification."""

    FACTUAL = "factual"
    EXPLORATORY = "exploratory"
    CLARIFICATION = "clarification"
    META = "meta"


class MessageIntent(str, Enum):
    """Intent of a message within an exploration."""

    FOLLOWUP_QUESTION = "followup_question"
    NAVIGATION_COMMAND = "navigation_command"
    ANALYSIS_REQUEST = "analysis_request"


class NavigationTarget(str, Enum):
    """Target for navigation commands."""

    NEXT = "next"
    PREVIOUS = "previous"
    BACK = "back"
    OVERVIEW = "overview"
