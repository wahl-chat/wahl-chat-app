# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Facade for guided exploration - public module interface."""

import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from typing import Literal


from src.guided_exploration.agents import (
    AnalyzerAgent,
    ContentGeneratorAgent,
    ConversationHandlerAgent,
    MessageClassifierAgent,
    QueryClassifierAgent,
    SummaryGeneratorAgent,
    TopicScoutAgent,
)
from src.guided_exploration.agents.llm_provider import (
    LLMRegistry,
    LLMTier,
    LangChainLLMProvider,
)
from src.guided_exploration.api.sse import SSEManager, get_sse_manager
from src.guided_exploration.handlers.analysis import AnalysisHandler
from src.guided_exploration.handlers.choice_flow import ChoiceFlowHandler
from src.guided_exploration.handlers.exploration_lifecycle import (
    ExplorationLifecycleHandler,
)
from src.guided_exploration.handlers.factual_query import FactualQueryHandler
from src.guided_exploration.handlers.followup import FollowupHandler
from src.guided_exploration.handlers.inbound_router import InboundRouter
from src.guided_exploration.handlers.navigation import (
    NavigationHandler,
)
from src.guided_exploration.handlers.quick_summary import QuickSummaryHandler
from src.guided_exploration.models import (
    SessionInfo,
    SessionMode,
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
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_exposure import StudyExposureLogger
from src.guided_exploration.services.session_repository import (
    SessionRepository,
    get_session_repository,
)
from src.llms import openai_gpt_5_4, openai_gpt_5_4_mini

logger = logging.getLogger(__name__)

# Pre-gen leaf timeout: two LLM calls in sequence (structured gen + aspect
# extraction); 45 s leaves headroom for slow-tail latency.
LEAF_PREGEN_TIMEOUT_SECONDS = 45.0


class GuidedExplorationFacade:
    """
    Public interface for guided exploration module.

    Coordinates between SSE manager, session repository, and orchestrator.
    """

    def __init__(
        self,
        sse_manager: SSEManager,
        repository: SessionRepository,
        llm_registry: LLMRegistry,
    ) -> None:
        self._sse = sse_manager
        self._streaming = StreamingService(sse_manager)
        self._repo = repository
        self._llm_registry = llm_registry

        # RAG service for direct retrieval (quick summary, factual queries)
        self._rag_service = RAGService(embeddings=llm_registry.embeddings)

        # Pass registry to orchestrator (handles topic resolution agents)
        self._orchestrator = Orchestrator(sse_manager, self._llm_registry)

        # Query classification is simple - use fast model
        self._query_classifier = QueryClassifierAgent(
            self._llm_registry.get(LLMTier.FAST)
        )
        # Message classification within exploration - use fast model
        self._message_classifier = MessageClassifierAgent(
            self._llm_registry.get(LLMTier.FAST)
        )
        # Content generation needs quality - use balanced model
        # Aspect extraction uses fast model for speed
        self._content_generator = ContentGeneratorAgent(
            self._llm_registry.get(LLMTier.BALANCED),
            fast_llm_provider=self._llm_registry.get(LLMTier.FAST),
        )
        # Conversation handling needs understanding - use balanced model
        self._conversation_handler = ConversationHandlerAgent(
            self._llm_registry.get(LLMTier.BALANCED)
        )
        # Analysis requires deep reasoning
        self._analyzer = AnalyzerAgent(self._llm_registry.get(LLMTier.REASONING))
        # Summary generation - balanced model
        self._summary_generator = SummaryGeneratorAgent(
            self._llm_registry.get(LLMTier.BALANCED)
        )
        # Followup routing - fast model for minimal latency
        from src.guided_exploration.agents.followup_router import (
            FollowupRouterAgent,
        )
        self._followup_router = FollowupRouterAgent(
            self._llm_registry.get(LLMTier.FAST)
        )
        # Topic scouting - fast model for direction identification
        self._topic_scout = TopicScoutAgent(
            self._llm_registry.get(LLMTier.FAST)
        )

        # State stores
        self._pending_queries = PendingQueryStore()
        self._navigation_states = NavigationStateStore()
        self._context_resolver = ContextResolver()
        self._directions_cache = DirectionsCache()
        self._study_exposure = StudyExposureLogger(repository)

        # Registry of in-flight study pre-gen tasks, keyed by
        # (exploration_id, leaf_id). When a user opens a leaf whose
        # content is still being pre-generated, navigate_to_leaf awaits
        # the in-flight task instead of firing a duplicate LLM call.
        # S8: if a second tab claims the session while pre-gen is running for
        # the first tab, in-flight sse.send_to_session calls silently no-op
        # (return False) because the SSE connection was closed on claim. This
        # is acceptable — the new tab will re-trigger generation on its own
        # navigation.
        self._pregen_leaf_tasks: dict[tuple[str, str], asyncio.Task] = {}

        # Workflow handlers
        self._analysis_handler = AnalysisHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            context_resolver=self._context_resolver,
            navigation_states=self._navigation_states,
            analyzer=self._analyzer,
        )
        self._quick_summary_handler = QuickSummaryHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            rag_service=self._rag_service,
            context_resolver=self._context_resolver,
            summary_generator=self._summary_generator,
            study_exposure=self._study_exposure,
        )
        self._factual_query_handler = FactualQueryHandler(
            repo=repository,
            streaming=self._streaming,
            rag_service=self._rag_service,
            context_resolver=self._context_resolver,
            conversation_handler=self._conversation_handler,
            summary_generator=self._summary_generator,
            study_exposure=self._study_exposure,
            get_default_parties=self._context_resolver.get_default_parties,
        )
        self._navigation_handler = NavigationHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            context_resolver=self._context_resolver,
            navigation_states=self._navigation_states,
            content_generator=self._content_generator,
            pregen_leaf_tasks=self._pregen_leaf_tasks,
            study_exposure=self._study_exposure,
        )
        self._followup_handler = FollowupHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            rag_service=self._rag_service,
            context_resolver=self._context_resolver,
            navigation_states=self._navigation_states,
            navigation_handler=self._navigation_handler,
            message_classifier=self._message_classifier,
            followup_router=self._followup_router,
            conversation_handler=self._conversation_handler,
            summary_generator=self._summary_generator,
            study_exposure=self._study_exposure,
        )

        # All fire-and-forget tasks created via asyncio.create_task. Completed
        # tasks remove themselves via add_done_callback. Used by cleanup() to
        # cancel pending tasks on shutdown.
        self._background_tasks: set[asyncio.Task] = set()

        self._exploration_lifecycle = ExplorationLifecycleHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            context_resolver=self._context_resolver,
            navigation_states=self._navigation_states,
            orchestrator=self._orchestrator,
            content_generator=self._content_generator,
            summary_generator=self._summary_generator,
            pregen_leaf_tasks=self._pregen_leaf_tasks,
            background_tasks=self._background_tasks,
        )
        self._choice_flow = ChoiceFlowHandler(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            rag_service=self._rag_service,
            context_resolver=self._context_resolver,
            pending_queries=self._pending_queries,
            directions_cache=self._directions_cache,
            topic_scout=self._topic_scout,
            quick_summary_handler=self._quick_summary_handler,
            exploration_lifecycle=self._exploration_lifecycle,
        )
        self._inbound_router = InboundRouter(
            repo=repository,
            sse=sse_manager,
            streaming=self._streaming,
            context_resolver=self._context_resolver,
            query_classifier=self._query_classifier,
            llm_registry=self._llm_registry,
            choice_flow=self._choice_flow,
            quick_summary_handler=self._quick_summary_handler,
            factual_query_handler=self._factual_query_handler,
            followup_handler=self._followup_handler,
        )

    def set_study_exposure_logger(
        self,
        logger_fn: "Callable[[str, list[str]], Awaitable[None]]",
    ) -> None:
        """Register a callback that persists cited position ids for study sessions.

        Invoked by handlers via ``StudyExposureLogger`` after the LLM cites
        sources — the callback typically resolves the chat id to a study
        session and merges the ids into ``condition.positions_encountered``.
        """
        self._study_exposure.register(logger_fn)

    async def create_session(
        self,
        context_id: str,
        user_id: str | None = None,
        mode: SessionMode = SessionMode.GUIDED,
        max_claims_per_party: int | None = None,
    ) -> SessionInfo:
        """Create a new guided exploration session."""
        session = await self._repo.create_session(
            context_id=context_id,
            user_id=user_id,
            mode=mode,
            max_claims_per_party=max_claims_per_party,
        )

        logger.info(
            f"Created session: {session.id} with mode={mode.value} "
            f"max_claims_per_party={max_claims_per_party}"
        )

        return SessionInfo(
            session_id=session.id,
            stream_url=f"/api/v1/guided-exploration/sessions/{session.id}/stream",
            active_exploration=None,
        )

    async def get_session(self, session_id: str) -> dict | None:
        """Get session data for resuming."""
        session = await self._repo.get_session(session_id)
        if not session:
            return None

        # Update activity timestamp
        await self._repo.update_session_activity(session_id)

        # Get active exploration if any
        active_exploration = await self._repo.get_active_exploration(session_id)

        # Get session messages
        messages = [msg.model_dump(mode="json") for msg in session.messages]

        # Get all explorations
        explorations = await self._repo.list_explorations(session_id)

        result: dict = {
            "session_id": session_id,
            "context_id": session.context_id,
            "user_id": session.user_id,
            "active_exploration": None,
            "navigation_state": None,
            "messages": messages,
            "explorations": explorations,
        }

        if active_exploration:
            result["active_exploration"] = {
                "id": active_exploration.id,
                "original_query": active_exploration.original_query,
                "status": active_exploration.status.value,
                "tree": active_exploration.tree.model_dump(mode="json"),
            }

            # Include navigation state if we have one cached
            nav_state = self._navigation_states.get(session_id)
            if nav_state:
                result["navigation_state"] = nav_state.model_dump(mode="json")

        return result

    async def get_exploration_conversations(
        self,
        session_id: str,
        exploration_id: str,
    ) -> list:
        """
        Get all conversations for an exploration.

        Args:
            session_id: The session ID
            exploration_id: The exploration ID

        Returns:
            List of Conversation objects
        """
        return await self._repo.list_conversations(session_id, exploration_id)

    async def handle_message(
        self,
        session_id: str,
        content: str,
        exploration_context: dict | None = None,
    ) -> dict:
        return await self._inbound_router.handle_message(
            session_id, content, exploration_context
        )

    async def handle_direction_choice(
        self,
        session_id: str,
        query_id: str,
        directions: list[dict],
    ) -> dict:
        return await self._choice_flow.handle_direction_choice(
            session_id, query_id, directions
        )

    async def handle_choice(
        self,
        session_id: str,
        query_id: str,
        choice: Literal["explore", "summary"],
        parties: list[str] | None = None,
    ) -> dict:
        return await self._choice_flow.handle_choice(
            session_id, query_id, choice, parties
        )

    async def start_exploration(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
    ) -> dict:
        return await self._exploration_lifecycle.start_exploration(
            session_id=session_id,
            query=query,
            context_id=context_id,
            parties=parties,
        )

    async def navigate(
        self,
        session_id: str,
        exploration_id: str,
        target_path: list[str],
    ) -> dict:
        return await self._navigation_handler.navigate(
            session_id, exploration_id, target_path
        )

    async def mark_explored(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        return await self._exploration_lifecycle.mark_explored(
            session_id, exploration_id, leaf_id
        )

    async def handle_followup(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
        user_message: str,
    ) -> dict:
        return await self._followup_handler.handle(
            session_id, exploration_id, leaf_id, user_message
        )

    async def list_explorations(self, session_id: str) -> list[dict]:
        """List all explorations for a session."""
        return await self._repo.list_explorations(session_id)

    async def get_exploration(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        """Get a specific exploration with its full tree."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            return None

        return {
            "id": exploration.id,
            "original_query": exploration.original_query,
            "status": exploration.status.value,
            "tree": exploration.tree.model_dump(mode="json"),
            "created_at": exploration.created_at.isoformat()
            if exploration.created_at
            else None,
        }

    async def get_knowledge_base(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        """Get the knowledge base for an exploration (for debugging)."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            return None

        # Return positions from the exploration tree for debugging
        return {
            "exploration_id": exploration_id,
            "positions": {
                cid: c.model_dump(mode="json")
                for cid, c in exploration.tree.positions.items()
            },
        }

    async def request_analysis(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        return await self._analysis_handler.request_analysis(
            session_id, exploration_id, leaf_id
        )

    async def cleanup(self) -> None:
        """Cancel all pending background tasks and await their completion.

        Wired into the aiohttp ``on_cleanup`` lifecycle by
        ``setup_guided_exploration_routes`` so in-flight pre-gen tasks are
        cancelled gracefully on server shutdown.
        """
        pending = {t for t in self._background_tasks if not t.done()}
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        logger.info(f"GuidedExplorationFacade cleanup: cancelled {len(pending)} tasks")

    async def end_exploration(
        self,
        session_id: str,
        exploration_id: str,
        generate_summary: bool = True,
    ) -> dict:
        return await self._exploration_lifecycle.end_exploration(
            session_id, exploration_id, generate_summary
        )


# Singleton instance
_facade: GuidedExplorationFacade | None = None
# N6: threading.Lock prevents double-init under concurrent cold-start requests
# (safe in single-threaded asyncio; the lock is only contested at first call).
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
                # classification AND structured content rendering — the leaf
                # summaries and hierarchy construction are template-shaped
                # tasks with all facts provided, where the flagship's extra
                # reasoning headroom buys nothing. gpt-5.4 is reserved for
                # the analyzer, which does open-ended judgment over conversation
                # history.
                registry = LLMRegistry()
                registry.register(LLMTier.FAST, LangChainLLMProvider(openai_gpt_5_4_mini))
                registry.register(LLMTier.BALANCED, LangChainLLMProvider(openai_gpt_5_4_mini))
                registry.register(LLMTier.REASONING, LangChainLLMProvider(openai_gpt_5_4))
                registry.set_embeddings(LLMRegistry.create_openai_embeddings())

                _facade = GuidedExplorationFacade(sse_manager, repository, registry)
    return _facade
