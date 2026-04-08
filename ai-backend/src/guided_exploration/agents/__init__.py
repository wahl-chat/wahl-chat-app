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
- ContentGeneratorAgent: Generates streaming leaf content (BALANCED tier)
- ConversationHandlerAgent: Handles follow-up conversations (BALANCED tier)
- AnalyzerAgent: Generates streaming critical analysis (REASONING tier)
- SummaryGeneratorAgent: Generates various summary types (BALANCED tier)
"""

from src.guided_exploration.agents.analyzer import AnalyzerAgent, AnalyzerInput
from src.guided_exploration.agents.base import (
    AgentError,
    AgentExecutionError,
    AgentValidationError,
    BaseAgent,
    StreamingAgent,
)
from src.guided_exploration.agents.position_extractor import (
    PositionExtractorAgent,
    PositionExtractorInput,
    PositionExtractorOutput,
)
from src.guided_exploration.agents.content_generator import (
    ContentGeneratorAgent,
    ContentGeneratorInput,
)
from src.guided_exploration.agents.conversation_handler import (
    ConversationHandlerAgent,
    ConversationHandlerInput,
    ConversationHandlerOutput,
)
from src.guided_exploration.agents.followup_router import (
    FollowupRoute,
    FollowupRouterAgent,
    FollowupRouterInput,
    FollowupRouterOutput,
    LeafInfo,
)
from src.guided_exploration.agents.hierarchy_builder import (
    HierarchyBuilderAgent,
    HierarchyBuilderInput,
    HierarchyBuilderOutput,
)
from src.guided_exploration.agents.llm_provider import (
    EMBEDDING_DIMENSION,
    LangChainLLMProvider,
    LLMProvider,
    LLMRegistry,
    LLMTier,
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
from src.guided_exploration.agents.summary_generator import (
    FinalSummaryInput,
    LeafSummaryInput,
    QuickSummaryInput,
    QuickSummaryOutput,
    SummaryGeneratorAgent,
    SummaryInput,
    SummaryOutput,
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
    # Content Generator
    "ContentGeneratorAgent",
    "ContentGeneratorInput",
    # Conversation Handler
    "ConversationHandlerAgent",
    "ConversationHandlerInput",
    "ConversationHandlerOutput",
    # Analyzer
    "AnalyzerAgent",
    "AnalyzerInput",
    # Summary Generator
    "SummaryGeneratorAgent",
    "SummaryInput",
    "SummaryOutput",
    "LeafSummaryInput",
    "QuickSummaryInput",
    "QuickSummaryOutput",
    "FinalSummaryInput",
    # Topic Scout
    "TopicScoutAgent",
    "TopicDirection",
    "TopicScoutInput",
    "TopicScoutOutput",
]
