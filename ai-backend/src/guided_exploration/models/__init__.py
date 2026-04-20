# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Re-export all model classes for easy imports."""

from src.guided_exploration.models.position import Position, PartyPositions
from src.guided_exploration.models.classification import (
    MessageClassificationInput,
    MessageClassificationOutput,
    MessageIntent,
    NavigationTarget,
    QueryClassificationInput,
    QueryClassificationOutput,
    QueryType,
)
from src.guided_exploration.models.content import (
    Analysis,
    Citation,
    PartyPosition,
    SubtopicContent,
)
from src.guided_exploration.models.conversation import (
    Conversation,
    LeafSummary,
    Message,
    MessageRole,
    MessageType,
)
from src.guided_exploration.models.errors import (
    AuthorizationError,
    ExplorationNotFoundError,
    ExportGenerationError,
    GuidedExplorationError,
    InsufficientChunksError,
    InvalidNavigationError,
    SessionNotFoundError,
)
from src.guided_exploration.models.events import (
    AnalysisResultEvent,
    ChatMessageEvent,
    ChoicePromptEvent,
    ConnectedEvent,
    ConversationMessageEvent,
    ConversationOpenedEvent,
    ErrorEvent,
    ExplorationCompleteEvent,
    ExplorationReadyEvent,
    ExportReadyEvent,
    QuickSummaryEvent,
    ReconnectedEvent,
    SessionClaimedEvent,
    SSEEvent,
    StreamChunkEvent,
    StreamEndEvent,
    SummaryGeneratingEvent,
    ThinkingEvent,
    TopicDirectionItem,
    TopicDirectionsEvent,
    TopicOverviewEvent,
    TopicTreeEvent,
)
from src.guided_exploration.models.exploration import (
    Exploration,
    ExplorationStatus,
    ExtractedPositionItem,
    ExtractedPosition,
    FinalSummary,
    ResolvedKnowledge,
    RetrievedChunk,
    SummaryTree,
)
from src.guided_exploration.models.navigation import (
    BreadcrumbItem,
    BreadcrumbLevel,
    NavigationState,
    SiblingNavigation,
)
from src.guided_exploration.models.session import (
    ExplorationContext,
    ExportOptions,
    ExportResult,
    PartialStream,
    Session,
    SessionInfo,
    SessionMessage,
    SessionMessageType,
    SessionMode,
    SessionReconnectState,
)
from src.guided_exploration.models.streaming import StreamChunk
from src.guided_exploration.models.tree import (
    ExplorationNode,
    ExplorationTree,
    NodeStatus,
)

__all__ = [
    # position
    "Position",
    "PartyPositions",
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
    "InsufficientChunksError",
    "InvalidNavigationError",
    "SessionNotFoundError",
    # events
    "AnalysisResultEvent",
    "ChatMessageEvent",
    "ChoicePromptEvent",
    "ConnectedEvent",
    "ConversationMessageEvent",
    "ConversationOpenedEvent",
    "ErrorEvent",
    "ExplorationCompleteEvent",
    "ExplorationReadyEvent",
    "ExportReadyEvent",
    "QuickSummaryEvent",
    "ReconnectedEvent",
    "SessionClaimedEvent",
    "SSEEvent",
    "StreamChunkEvent",
    "StreamEndEvent",
    "SummaryGeneratingEvent",
    "ThinkingEvent",
    "TopicDirectionItem",
    "TopicDirectionsEvent",
    "TopicOverviewEvent",
    "TopicTreeEvent",
    # exploration
    "Exploration",
    "ExplorationStatus",
    "ExtractedPositionItem",
    "ExtractedPosition",
    "FinalSummary",
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
    "SessionMessage",
    "SessionMessageType",
    "SessionMode",
    "SessionReconnectState",
    # streaming
    "StreamChunk",
    # tree
    "ExplorationNode",
    "ExplorationTree",
    "NodeStatus",
]
