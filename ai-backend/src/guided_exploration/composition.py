# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Composition root: wire the facade and its dependency graph.

Holds the DI block and the singleton accessor that previously lived
inside ``facade.py``. Keeping this here lets ``facade.py`` stay a thin
dispatch layer.
"""

import asyncio
import logging
import threading

from src.guided_exploration.agents import (
    AnalyzerAgent,
    BaselineAgent,
    LeafContentGeneratorAgent,
    LeafConversationHandlerAgent,
    LeafFollowUpGenerator,
    MainChatFollowUpGenerator,
    MessageClassifierAgent,
    QueryClassifierAgent,
    QuickSummaryAgent,
    TopicScoutAgent,
)
from src.guided_exploration.agents.llm_provider import (
    LLMRegistry,
    LLMTier,
    LangChainLLMProvider,
)
from src.guided_exploration.api.sse import SSEManager, get_sse_manager
from src.guided_exploration.facade import GuidedExplorationFacade
from src.guided_exploration.handlers.analysis import AnalysisHandler
from src.guided_exploration.handlers.baseline import BaselineHandler
from src.guided_exploration.handlers.choice_flow import ChoiceFlowHandler
from src.guided_exploration.handlers.exploration_lifecycle import (
    ExplorationLifecycleHandler,
)
from src.guided_exploration.handlers.inbound_router import InboundRouter
from src.guided_exploration.handlers.leaf_conversation import (
    LeafConversationHandler,
)
from src.guided_exploration.handlers.navigation import NavigationHandler
from src.guided_exploration.handlers.quick_summary import QuickSummaryHandler
from src.guided_exploration.services.background_tasks import (
    BackgroundTaskRegistry,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.directions_cache import DirectionsCache
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.orchestrator import Orchestrator
from src.guided_exploration.services.pending_query_store import (
    PendingQueryStore,
)
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.session_repository import (
    SessionRepository,
    get_session_repository,
)
from src.guided_exploration.services.session_service import SessionService
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_exposure import StudyExposureLogger
from src.llms import openai_gpt_5_4, openai_gpt_5_4_mini

logger = logging.getLogger(__name__)


def build_facade(
    sse_manager: SSEManager,
    repository: SessionRepository,
    llm_registry: LLMRegistry,
) -> GuidedExplorationFacade:
    """Construct the full facade dependency graph."""
    streaming = StreamingService(sse_manager)
    rag_service = RAGService(embeddings=llm_registry.embeddings)
    orchestrator = Orchestrator(sse_manager, llm_registry)

    # Agents
    query_classifier = QueryClassifierAgent(llm_registry.get(LLMTier.FAST))
    message_classifier = MessageClassifierAgent(llm_registry.get(LLMTier.FAST))
    content_generator = LeafContentGeneratorAgent(
        llm_registry.get(LLMTier.BALANCED),
        fast_llm_provider=llm_registry.get(LLMTier.FAST),
    )
    conversation_handler = LeafConversationHandlerAgent(
        llm_registry.get(LLMTier.BALANCED)
    )
    analyzer = AnalyzerAgent(llm_registry.get(LLMTier.REASONING))
    quick_summary_agent = QuickSummaryAgent(llm_registry.get(LLMTier.BALANCED))
    baseline_agent = BaselineAgent(llm_registry.get(LLMTier.BALANCED))
    main_chat_followup_generator = MainChatFollowUpGenerator(
        llm_registry.get(LLMTier.FAST)
    )
    leaf_followup_generator = LeafFollowUpGenerator(
        llm_registry.get(LLMTier.FAST)
    )
    topic_scout = TopicScoutAgent(llm_registry.get(LLMTier.FAST))

    # State stores / shared services
    pending_queries = PendingQueryStore()
    navigation_states = NavigationStateStore()
    context_resolver = ContextResolver()
    directions_cache = DirectionsCache()
    study_exposure = StudyExposureLogger(repository)

    # Pre-gen task accounting (keyed by exploration_id + leaf_id) — kept
    # separate from the generic background-task registry because lookups
    # are by composite key, not just a flat set.
    pregen_leaf_tasks: dict[tuple[str, str], asyncio.Task] = {}
    background_tasks = BackgroundTaskRegistry()

    # Session-level read/write surface
    session_service = SessionService(
        repo=repository,
        navigation_states=navigation_states,
    )

    # Workflow handlers
    analysis_handler = AnalysisHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        context_resolver=context_resolver,
        navigation_states=navigation_states,
        analyzer=analyzer,
    )
    quick_summary_handler = QuickSummaryHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        rag_service=rag_service,
        context_resolver=context_resolver,
        quick_summary_agent=quick_summary_agent,
        main_chat_followup_generator=main_chat_followup_generator,
        study_exposure=study_exposure,
    )
    baseline_handler = BaselineHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        rag_service=rag_service,
        context_resolver=context_resolver,
        baseline_agent=baseline_agent,
        main_chat_followup_generator=main_chat_followup_generator,
        study_exposure=study_exposure,
    )
    navigation_handler = NavigationHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        context_resolver=context_resolver,
        navigation_states=navigation_states,
        content_generator=content_generator,
        pregen_leaf_tasks=pregen_leaf_tasks,
        study_exposure=study_exposure,
    )
    leaf_conversation_handler = LeafConversationHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        rag_service=rag_service,
        context_resolver=context_resolver,
        navigation_states=navigation_states,
        navigation_handler=navigation_handler,
        message_classifier=message_classifier,
        conversation_handler=conversation_handler,
        leaf_followup_generator=leaf_followup_generator,
        study_exposure=study_exposure,
    )
    exploration_lifecycle = ExplorationLifecycleHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        context_resolver=context_resolver,
        navigation_states=navigation_states,
        orchestrator=orchestrator,
        content_generator=content_generator,
        pregen_leaf_tasks=pregen_leaf_tasks,
        background_tasks=background_tasks,
    )
    choice_flow = ChoiceFlowHandler(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        rag_service=rag_service,
        context_resolver=context_resolver,
        pending_queries=pending_queries,
        directions_cache=directions_cache,
        topic_scout=topic_scout,
        quick_summary_handler=quick_summary_handler,
        exploration_lifecycle=exploration_lifecycle,
    )
    inbound_router = InboundRouter(
        repo=repository,
        sse=sse_manager,
        streaming=streaming,
        context_resolver=context_resolver,
        query_classifier=query_classifier,
        llm_registry=llm_registry,
        choice_flow=choice_flow,
        baseline_handler=baseline_handler,
        quick_summary_handler=quick_summary_handler,
        leaf_conversation_handler=leaf_conversation_handler,
    )

    return GuidedExplorationFacade(
        session_service=session_service,
        inbound_router=inbound_router,
        choice_flow=choice_flow,
        exploration_lifecycle=exploration_lifecycle,
        navigation_handler=navigation_handler,
        leaf_conversation_handler=leaf_conversation_handler,
        analysis_handler=analysis_handler,
        background_tasks=background_tasks,
        study_exposure=study_exposure,
    )


_facade: GuidedExplorationFacade | None = None
_facade_lock = threading.Lock()


def get_facade() -> GuidedExplorationFacade:
    """Get or create the global facade (thread-safe singleton)."""
    global _facade
    if _facade is None:
        with _facade_lock:
            if _facade is None:
                sse_manager = get_sse_manager()
                repository = get_session_repository()

                # GPT-5.4 family (March 2026 flagship). gpt-5.4-mini handles
                # classification AND structured content rendering; gpt-5.4 is
                # reserved for the analyzer's open-ended judgment over
                # conversation history.
                registry = LLMRegistry()
                registry.register(
                    LLMTier.FAST, LangChainLLMProvider(openai_gpt_5_4_mini)
                )
                registry.register(
                    LLMTier.BALANCED, LangChainLLMProvider(openai_gpt_5_4_mini)
                )
                registry.register(
                    LLMTier.REASONING, LangChainLLMProvider(openai_gpt_5_4)
                )
                registry.set_embeddings(LLMRegistry.create_openai_embeddings())

                _facade = build_facade(sse_manager, repository, registry)
    return _facade
