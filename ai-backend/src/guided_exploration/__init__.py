# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Guided Exploration Module.

Position-based adaptive hierarchy for exploring party positions
on political topics with conversational followups and analysis.
"""

# Re-export facade
from src.guided_exploration.composition import get_facade
from src.guided_exploration.facade import GuidedExplorationFacade

# Re-export services
from src.guided_exploration.services import (
    Orchestrator,
    SessionRepository,
    get_session_repository,
)

# Re-export all models for easy access
from src.guided_exploration.models import (
    # position
    Position,
    PartyPositions,
    # classification
    MessageIntent,
    NavigationTarget,
    QueryType,
    # content
    Analysis,
    Citation,
    PartyPosition,
    SubtopicContent,
    # conversation
    Conversation,
    Message,
    MessageRole,
    MessageType,
    # errors
    AuthorizationError,
    ExplorationNotFoundError,
    GuidedExplorationError,
    InvalidNavigationError,
    SessionNotFoundError,
    # events
    ChoicePromptEvent,
    ConnectedEvent,
    ConversationMessageEvent,
    ConversationOpenedEvent,
    ErrorEvent,
    ExplorationCompleteEvent,
    QuickSummaryEvent,
    SessionClaimedEvent,
    SSEEvent,
    StreamChunkEvent,
    StreamEndEvent,
    ThinkingEvent,
    TopicOverviewEvent,
    TopicTreeEvent,
    # exploration
    Exploration,
    ExplorationStatus,
    ResolvedKnowledge,
    RetrievedChunk,
    # navigation
    BreadcrumbItem,
    BreadcrumbLevel,
    NavigationState,
    SiblingNavigation,
    # session
    Session,
    SessionInfo,
    # streaming
    StreamChunk,
    # tree
    ExplorationNode,
    ExplorationTree,
)

__all__ = [
    # facade
    "GuidedExplorationFacade",
    "get_facade",
    # services
    "Orchestrator",
    "SessionRepository",
    "get_session_repository",
    # position
    "Position",
    "PartyPositions",
    # classification
    "MessageIntent",
    "NavigationTarget",
    "QueryType",
    # content
    "Analysis",
    "Citation",
    "PartyPosition",
    "SubtopicContent",
    # conversation
    "Conversation",
    "Message",
    "MessageRole",
    "MessageType",
    # errors
    "AuthorizationError",
    "ExplorationNotFoundError",
    "GuidedExplorationError",
    "InvalidNavigationError",
    "SessionNotFoundError",
    # events
    "ChoicePromptEvent",
    "ConnectedEvent",
    "ConversationMessageEvent",
    "ConversationOpenedEvent",
    "ErrorEvent",
    "ExplorationCompleteEvent",
    "QuickSummaryEvent",
    "SessionClaimedEvent",
    "SSEEvent",
    "StreamChunkEvent",
    "StreamEndEvent",
    "ThinkingEvent",
    "TopicOverviewEvent",
    "TopicTreeEvent",
    # exploration
    "Exploration",
    "ExplorationStatus",
    "ResolvedKnowledge",
    "RetrievedChunk",
    # navigation
    "BreadcrumbItem",
    "BreadcrumbLevel",
    "NavigationState",
    "SiblingNavigation",
    # session
    "Session",
    "SessionInfo",
    # streaming
    "StreamChunk",
    # tree
    "ExplorationNode",
    "ExplorationTree",
]
