# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Guided Exploration Module.

Claim-based adaptive hierarchy for exploring party positions
on political topics with conversational followups and analysis.
"""

# Re-export facade
from src.guided_exploration.facade import GuidedExplorationFacade, get_facade

# Re-export services
from src.guided_exploration.services import (
    Orchestrator,
    SessionRepository,
    get_session_repository,
)

# Re-export all models for easy access
from src.guided_exploration.models import (
    # claim
    Claim,
    PartyClaims,
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
    # claim
    "Claim",
    "PartyClaims",
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
    "ExplorationNode",
    "ExplorationTree",
]
