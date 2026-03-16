# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Guided Exploration Module.

This module provides structured, tree-based exploration of political topics
with conversational followups and analysis capabilities.
"""

# Re-export facade
from src.guided_exploration.facade import GuidedExplorationFacade, get_facade

# Re-export services
from src.guided_exploration.services import (
    Orchestrator,
    SessionRepository,
    get_session_repository,
    merge_party_knowledge,
)

# Re-export all models for easy access
from src.guided_exploration.models import (
    # classification
    MessageClassificationInput,
    MessageClassificationOutput,
    MessageIntent,
    NavigationTarget,
    QueryClassificationInput,
    QueryClassificationOutput,
    QueryType,
    # content
    Analysis,
    Citation,
    PartyPosition,
    SubtopicContent,
    # conversation
    Conversation,
    LeafSummary,
    Message,
    MessageRole,
    MessageType,
    # errors
    AuthorizationError,
    ExplorationNotFoundError,
    ExportGenerationError,
    GuidedExplorationError,
    InvalidNavigationError,
    SessionNotFoundError,
    # events
    AnalysisResultEvent,
    ChoicePromptEvent,
    ConnectedEvent,
    ConversationMessageEvent,
    ConversationOpenedEvent,
    ErrorEvent,
    ExplorationCompleteEvent,
    ExportReadyEvent,
    QuickSummaryEvent,
    ReconnectedEvent,
    SessionClaimedEvent,
    SSEEvent,
    StreamChunkEvent,
    StreamEndEvent,
    SummaryGeneratingEvent,
    ThinkingEvent,
    TopicOverviewEvent,
    TopicTreeEvent,
    # exploration
    Exploration,
    ExplorationStatus,
    FinalSummary,
    KnowledgeBase,
    ResolvedKnowledge,
    RetrievedChunk,
    SummaryTree,
    # navigation
    BreadcrumbItem,
    BreadcrumbLevel,
    NavigationState,
    SiblingNavigation,
    # session
    ExplorationContext,
    ExportOptions,
    ExportResult,
    PartialStream,
    Session,
    SessionInfo,
    SessionReconnectState,
    # streaming
    StreamChunk,
    # tree
    Subtopic,
    Topic,
    TopicTree,
)

__all__ = [
    # facade
    "GuidedExplorationFacade",
    "get_facade",
    # services
    "merge_party_knowledge",
    "Orchestrator",
    "SessionRepository",
    "get_session_repository",
    # classification
    "MessageClassificationInput",
    "MessageClassificationOutput",
    "MessageIntent",
    "NavigationTarget",
    "QueryClassificationInput",
    "QueryClassificationOutput",
    "QueryType",
    # content
    "Analysis",
    "Citation",
    "PartyPosition",
    "SubtopicContent",
    # conversation
    "Conversation",
    "LeafSummary",
    "Message",
    "MessageRole",
    "MessageType",
    # errors
    "AuthorizationError",
    "ExplorationNotFoundError",
    "ExportGenerationError",
    "GuidedExplorationError",
    "InvalidNavigationError",
    "SessionNotFoundError",
    # events
    "AnalysisResultEvent",
    "ChoicePromptEvent",
    "ConnectedEvent",
    "ConversationMessageEvent",
    "ConversationOpenedEvent",
    "ErrorEvent",
    "ExplorationCompleteEvent",
    "ExportReadyEvent",
    "QuickSummaryEvent",
    "ReconnectedEvent",
    "SessionClaimedEvent",
    "SSEEvent",
    "StreamChunkEvent",
    "StreamEndEvent",
    "SummaryGeneratingEvent",
    "ThinkingEvent",
    "TopicOverviewEvent",
    "TopicTreeEvent",
    # exploration
    "Exploration",
    "ExplorationStatus",
    "FinalSummary",
    "KnowledgeBase",
    "ResolvedKnowledge",
    "RetrievedChunk",
    "SummaryTree",
    # navigation
    "BreadcrumbItem",
    "BreadcrumbLevel",
    "NavigationState",
    "SiblingNavigation",
    # session
    "ExplorationContext",
    "ExportOptions",
    "ExportResult",
    "PartialStream",
    "Session",
    "SessionInfo",
    "SessionReconnectState",
    # streaming
    "StreamChunk",
    # tree
    "Subtopic",
    "Topic",
    "TopicTree",
]
