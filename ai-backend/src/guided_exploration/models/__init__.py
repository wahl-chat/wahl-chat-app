# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Re-export all model classes for easy imports."""

from src.guided_exploration.models.position import Position, PartyPositions
from src.guided_exploration.models.classification import (
    MessageIntent,
    NavigationTarget,
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
    Message,
    MessageRole,
    MessageType,
    TopicSwitchProposal,
)
from src.guided_exploration.models.errors import (
    AuthorizationError,
    ExplorationNotFoundError,
    GuidedExplorationError,
    InsufficientChunksError,
    InvalidNavigationError,
    SessionNotFoundError,
)
from src.guided_exploration.models.events import (
    ChatMessageEvent,
    ChoiceOption,
    ChoicePromptEvent,
    ConnectedEvent,
    ConversationMessageEvent,
    ConversationOpenedEvent,
    ErrorEvent,
    ExplorationCompleteEvent,
    ExplorationReadyEvent,
    QuickSummaryEvent,
    SessionClaimedEvent,
    SSEEvent,
    StreamChunkEvent,
    StreamEndEvent,
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
    ResolvedKnowledge,
    RetrievedChunk,
)
from src.guided_exploration.models.navigation import (
    BreadcrumbItem,
    BreadcrumbLevel,
    NavigationState,
    SiblingNavigation,
)
from src.guided_exploration.models.session import (
    FlaggedCitation,
    Session,
    SessionInfo,
    SessionMessage,
    SessionMessageType,
    SessionMode,
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
    "TopicSwitchProposal",
    # errors
    "AuthorizationError",
    "ExplorationNotFoundError",
    "GuidedExplorationError",
    "InsufficientChunksError",
    "InvalidNavigationError",
    "SessionNotFoundError",
    # events
    "ChatMessageEvent",
    "ChoiceOption",
    "ChoicePromptEvent",
    "ConnectedEvent",
    "ConversationMessageEvent",
    "ConversationOpenedEvent",
    "ErrorEvent",
    "ExplorationCompleteEvent",
    "ExplorationReadyEvent",
    "QuickSummaryEvent",
    "SessionClaimedEvent",
    "SSEEvent",
    "StreamChunkEvent",
    "StreamEndEvent",
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
    "ResolvedKnowledge",
    "RetrievedChunk",
    # navigation
    "BreadcrumbItem",
    "BreadcrumbLevel",
    "NavigationState",
    "SiblingNavigation",
    # session
    "FlaggedCitation",
    "Session",
    "SessionInfo",
    "SessionMessage",
    "SessionMessageType",
    "SessionMode",
    # streaming
    "StreamChunk",
    # tree
    "ExplorationNode",
    "ExplorationTree",
    "NodeStatus",
]
