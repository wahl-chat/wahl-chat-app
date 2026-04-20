# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Interface models for message classifier agent."""

from pydantic import BaseModel, Field

from src.guided_exploration.models.classification import MessageIntent, NavigationTarget


class MessageClassifierInput(BaseModel):
    """Input for message classification within an exploration."""

    message: str = Field(..., description="The user's message to classify")
    context_name: str = Field(
        ...,
        description="Human-readable name of the context (e.g., 'Bundestagswahl 2025', 'Kommunalwahl Hamburg')",
    )
    current_leaf_id: str | None = Field(
        default=None,
        description="Current leaf node ID if any",
    )
    exploration_id: str | None = Field(
        default=None,
        description="Current exploration ID if any",
    )
    conversation_history: list[str] = Field(
        default_factory=list,
        description="Previous messages for context (to resolve back-references)",
    )
    last_assistant_message: str | None = Field(
        default=None,
        description=(
            "The most recent assistant turn in full (untruncated). Surfaced "
            "separately so short affirmations like 'gerne' or 'ja' can be "
            "resolved against the specific question the assistant just asked."
        ),
    )


class MessageClassifierOutput(BaseModel):
    """Output from message classification."""

    intent: MessageIntent = Field(..., description="Classified intent of the message")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the classification"
    )
    navigation_target: NavigationTarget | None = Field(
        default=None,
        description="Navigation target if intent is navigation",
    )
    extracted_question: str | None = Field(
        default=None,
        description="Extracted question for followup intents",
    )
    target_id: str | None = Field(
        default=None,
        description="Target topic/subtopic ID for navigation or specific references",
    )
