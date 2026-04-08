# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Topic scout agent — identifies major subtopic directions from RAG chunks."""

from src.guided_exploration.agents.topic_scout.implementation import (
    TopicScoutAgent,
)
from src.guided_exploration.agents.topic_scout.interface import (
    TopicDirection,
    TopicScoutInput,
    TopicScoutOutput,
)

__all__ = [
    "TopicScoutAgent",
    "TopicDirection",
    "TopicScoutInput",
    "TopicScoutOutput",
]
