# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Agent interfaces and implementations for guided exploration.

Agent Types:
- PositionExtractorAgent: Extracts concrete positions from party documents
- HierarchyBuilderAgent: Builds adaptive tree from all positions
- QueryClassifierAgent: Classifies initial user queries (FAST tier)
- MessageClassifierAgent: Classifies messages within explorations (FAST tier)
- LeafContentGeneratorAgent: Generates streaming leaf content (BALANCED tier)
- LeafConversationHandlerAgent: Handles in-leaf follow-up conversations (BALANCED tier)
- AnalyzerAgent: Generates streaming critical analysis (REASONING tier)
- BaselineAgent: Streams baseline (production-wahl.chat-shaped) replies (BALANCED tier)
- QuickSummaryAgent: Streams guided main-chat replies (BALANCED tier)
- MainChatFollowUpGenerator: 3 fixed-slot follow-up chips for main chat (FAST)
- LeafFollowUpGenerator: leaf chips + closure + topic-switch proposal (FAST)
- TopicScoutAgent: Identifies topic directions for choice flow (FAST tier)
"""

from src.guided_exploration.agents.analyzer import AnalyzerAgent, AnalyzerInput
from src.guided_exploration.agents.base import (
    AgentError,
    AgentExecutionError,
    AgentValidationError,
    BaseAgent,
    StreamingAgent,
)
from src.guided_exploration.agents.baseline import (
    BaselineAgent,
    BaselineInput,
)
from src.guided_exploration.agents.position_extractor import (
    PositionExtractorAgent,
    PositionExtractorInput,
    PositionExtractorOutput,
)
from src.guided_exploration.agents.leaf_content_generator import (
    LeafContentGeneratorAgent,
    LeafContentGeneratorInput,
)
from src.guided_exploration.agents.leaf_conversation_handler import (
    LeafConversationHandlerAgent,
    LeafConversationHandlerInput,
)
from src.guided_exploration.agents.hierarchy_builder import (
    HierarchyBuilderAgent,
    HierarchyBuilderInput,
    HierarchyBuilderOutput,
)
from src.guided_exploration.agents.leaf_followup_generator import (
    LeafFollowUpGenerator,
    LeafFollowUpInput,
    LeafFollowUpResult,
    TopicSwitchProposal,
)
from src.guided_exploration.agents.llm_provider import (
    EMBEDDING_DIMENSION,
    LangChainLLMProvider,
    LLMProvider,
    LLMRegistry,
    LLMTier,
)
from src.guided_exploration.agents.main_chat_followup_generator import (
    MainChatFollowUpGenerator,
    MainChatFollowUpInput,
    MainChatFollowUpResult,
)
from src.guided_exploration.agents.message_classifier import (
    MessageClassifierAgent,
    MessageClassifierInput,
    MessageClassifierOutput,
)
from src.guided_exploration.agents.query_classifier import (
    QueryClassifierAgent,
    QueryClassifierInput,
    QueryClassifierOutput,
)
from src.guided_exploration.agents.quick_summary import (
    QuickSummaryAgent,
    QuickSummaryInput,
    QuickSummaryOutput,
)
from src.guided_exploration.agents.topic_scout import (
    TopicDirection,
    TopicScoutAgent,
    TopicScoutInput,
    TopicScoutOutput,
)

__all__ = [
    # Base interfaces
    "BaseAgent",
    "StreamingAgent",
    "AgentError",
    "AgentExecutionError",
    "AgentValidationError",
    # LLM Provider
    "EMBEDDING_DIMENSION",
    "LLMProvider",
    "LLMRegistry",
    "LLMTier",
    "LangChainLLMProvider",
    # Position Extractor
    "PositionExtractorAgent",
    "PositionExtractorInput",
    "PositionExtractorOutput",
    # Hierarchy Builder
    "HierarchyBuilderAgent",
    "HierarchyBuilderInput",
    "HierarchyBuilderOutput",
    # Query Classifier
    "QueryClassifierAgent",
    "QueryClassifierInput",
    "QueryClassifierOutput",
    # Message Classifier
    "MessageClassifierAgent",
    "MessageClassifierInput",
    "MessageClassifierOutput",
    # Leaf Content Generator
    "LeafContentGeneratorAgent",
    "LeafContentGeneratorInput",
    # Leaf Conversation Handler (in-leaf follow-up streamer)
    "LeafConversationHandlerAgent",
    "LeafConversationHandlerInput",
    # Analyzer
    "AnalyzerAgent",
    "AnalyzerInput",
    # Baseline (production-wahl.chat-shaped reply streamer)
    "BaselineAgent",
    "BaselineInput",
    # Quick Summary (guided main-chat reply streamer)
    "QuickSummaryAgent",
    "QuickSummaryInput",
    "QuickSummaryOutput",
    # Main-chat follow-up chips
    "MainChatFollowUpGenerator",
    "MainChatFollowUpInput",
    "MainChatFollowUpResult",
    # Leaf follow-up (chips + closure + topic-switch)
    "LeafFollowUpGenerator",
    "LeafFollowUpInput",
    "LeafFollowUpResult",
    "TopicSwitchProposal",
    # Topic Scout
    "TopicScoutAgent",
    "TopicDirection",
    "TopicScoutInput",
    "TopicScoutOutput",
]
