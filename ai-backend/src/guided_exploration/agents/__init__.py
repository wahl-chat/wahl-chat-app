# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Agent interfaces and implementations for guided exploration.

This module provides the agent abstraction layer with:
- Base interfaces (BaseAgent, StreamingAgent)
- LLM provider abstraction (LLMProvider, LLMRegistry, LLMTier)
- Specialized agents for different tasks

LLM Tiers:
- FAST: For simple classification tasks (gpt-5.2-mini, gemini-flash-lite)
- BALANCED: For most tasks requiring quality (gpt-5.2, gemini-flash)
- REASONING: For complex reasoning tasks (gpt-5.2, o3)

Agent Types:
- PartyTopicResolverAgent: Resolves topics from a single party's documents
- TopicCombinerAgent: Combines party topic trees into unified structure
- PartyKnowledgeResolverAgent: Resolves knowledge for a single party
- QueryClassifierAgent: Classifies initial user queries (FAST tier)
- MessageClassifierAgent: Classifies messages within explorations (FAST tier)
- ContentGeneratorAgent: Generates streaming subtopic content (BALANCED tier)
- ConversationHandlerAgent: Handles follow-up conversations (BALANCED tier)
- AnalyzerAgent: Generates streaming critical analysis (REASONING tier)
- SummaryGeneratorAgent: Generates various summary types (BALANCED tier)

Example usage with LLMRegistry:
    from src.guided_exploration.agents import (
        LLMRegistry,
        LLMTier,
        LangChainLLMProvider,
        QueryClassifierAgent,
    )
    from src.llms import gpt_5_2_mini, gpt_5_2

    # Create registry with different models for different tiers
    registry = LLMRegistry()
    registry.register(LLMTier.FAST, LangChainLLMProvider(gpt_5_2_mini))
    registry.register(LLMTier.BALANCED, LangChainLLMProvider(gpt_5_2))
    registry.register(LLMTier.REASONING, LangChainLLMProvider(gpt_5_2))

    # Use appropriate tier for each agent
    classifier = QueryClassifierAgent(registry.fast)
    result = await classifier.execute(input)
"""

from src.guided_exploration.agents.analyzer import AnalyzerAgent, AnalyzerInput
from src.guided_exploration.agents.base import (
    AgentError,
    AgentExecutionError,
    AgentValidationError,
    BaseAgent,
    StreamingAgent,
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
from src.guided_exploration.agents.knowledge_resolver import (
    PartyKnowledgeResolverAgent,
    PartyKnowledgeResolverInput,
    PartyKnowledgeResolverOutput,
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
from src.guided_exploration.agents.party_topic_resolver import (
    PartyTopicResolverAgent,
    PartyTopicResolverInput,
    PartyTopicResolverOutput,
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
from src.guided_exploration.agents.topic_combiner import (
    TopicCombinerAgent,
    TopicCombinerInput,
    TopicCombinerOutput,
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
    # Party Topic Resolver
    "PartyTopicResolverAgent",
    "PartyTopicResolverInput",
    "PartyTopicResolverOutput",
    # Topic Combiner
    "TopicCombinerAgent",
    "TopicCombinerInput",
    "TopicCombinerOutput",
    # Party Knowledge Resolver
    "PartyKnowledgeResolverAgent",
    "PartyKnowledgeResolverInput",
    "PartyKnowledgeResolverOutput",
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
]
