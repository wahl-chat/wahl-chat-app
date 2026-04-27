# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Facade for guided exploration - public module interface."""

import asyncio
import logging
import re
import time
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from src.firebase_service import aget_context_by_id, aget_parties_for_context
from src.guided_exploration.models.conversation import LeafSummary
from src.guided_exploration.models.exploration import FinalSummary

from src.guided_exploration.agents import (
    AnalyzerAgent,
    AnalyzerInput,
    ContentGeneratorAgent,
    ContentGeneratorInput,
    ConversationHandlerAgent,
    ConversationHandlerInput,
    MessageClassifierAgent,
    MessageClassifierInput,
    QueryClassifierAgent,
    QueryClassifierInput,
    SummaryGeneratorAgent,
    LeafSummaryInput,
    FinalSummaryInput,
    QuickSummaryInput,
    TopicScoutAgent,
    TopicScoutInput,
    LLMTier,
)
from src.guided_exploration.agents.party_context import (
    PartyInfo,
    parties_to_info_map,
)
from src.guided_exploration.models.classification import MessageIntent, NavigationTarget
from src.guided_exploration.services.citation_utils import (
    collect_leaf_citations,
    create_citation_from_chunk as create_chunk_citation,
    extract_used_citations,
)
from src.guided_exploration.models.errors import InsufficientChunksError
from src.guided_exploration.agents.llm_provider import (
    LLMRegistry,
    LLMTier,
    LangChainLLMProvider,
)
from src.guided_exploration.api.sse import SSEManager, get_sse_manager
from src.guided_exploration.models import (
    BreadcrumbItem,
    BreadcrumbLevel,
    ChoicePromptEvent,
    Citation,
    Conversation,
    ConversationMessageEvent,
    ConversationOpenedEvent,
    ErrorEvent,
    Exploration,
    ExplorationCompleteEvent,
    ExplorationNode,
    ExplorationTree,
    ExtractedPositionItem,
    ExtractedPosition,
    Message,
    MessageRole,
    MessageType,
    NavigationState,
    NodeStatus,
    QueryType,
    QuickSummaryEvent,
    ResolvedKnowledge,
    RetrievedChunk,
    SessionInfo,
    SessionMessage,
    SessionMessageType,
    SessionMode,
    SiblingNavigation,
    StreamChunkEvent,
    StreamEndEvent,
    SummaryGeneratingEvent,
    SummaryTree,
    ThinkingEvent,
    TopicDirectionItem,
    TopicDirectionsEvent,
    TopicOverviewEvent,
    ChatMessageEvent,
)
from src.guided_exploration.services.orchestrator import Orchestrator
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.study_context import (
    STUDY_PARTY_IDS,
    get_study_context_info,
    is_study_context,
)
from src.guided_exploration.services.session_repository import (
    SessionRepository,
    get_session_repository,
)
from src.llms import openai_gpt_5_4, openai_gpt_5_4_mini

logger = logging.getLogger(__name__)

# Streaming configuration
CHUNK_DELAY = 0.05  # 50ms between chunks
WORDS_PER_CHUNK = 5

# Context cache TTL: 1 hour. Context/party data changes infrequently; hourly
# refresh is more than sufficient.
_CONTEXT_CACHE_TTL_SECONDS = 3600

# Directions cache TTL: 6 hours. Scout outputs are stable for a topic; a
# longer TTL reduces LLM calls without meaningful staleness risk.
_DIRECTIONS_CACHE_TTL_SECONDS = 21600

# Pending-query TTL: 30 minutes. Abandoned sessions never call handle_choice,
# so entries must be evicted proactively to prevent unbounded growth.
_PENDING_QUERY_TTL_SECONDS = 1800

# Pre-gen leaf timeout: two LLM calls in sequence (structured gen + aspect
# extraction); 45 s leaves headroom for slow-tail latency.
LEAF_PREGEN_TIMEOUT_SECONDS = 45.0


class PendingQuery:
    """Tracks a pending query awaiting user choice."""

    def __init__(
        self,
        query_id: str,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
        selected_direction: str | None = None,
    ) -> None:
        self.query_id = query_id
        self.session_id = session_id
        self.original_query = original_query
        self.detected_parties = detected_parties
        self.rag_query = rag_query
        self.selected_direction = selected_direction
        self.created_at = datetime.now(timezone.utc)


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

        # In-memory tracking of pending queries (query_id -> PendingQuery)
        self._pending_queries: dict[str, PendingQuery] = {}

        # In-memory tracking of current navigation state per session
        self._navigation_states: dict[str, NavigationState] = {}

        # Cache for context info to avoid repeated Firebase calls
        # Maps context_id -> (timestamp, context_name, parties_info_map)
        self._context_cache: dict[str, tuple[float, str, dict[str, PartyInfo]]] = {}

        # Cache for topic directions — keyed by exact (query, context_id)
        # Maps key -> (timestamp, TopicScoutOutput)
        # Populated when the LLM flags a result as cacheable
        from src.guided_exploration.agents.topic_scout import TopicScoutOutput
        self._directions_cache: dict[tuple[str, str], tuple[float, TopicScoutOutput]] = {}

        # Registry of in-flight study pre-gen tasks, keyed by
        # (exploration_id, leaf_id). When a user opens a leaf whose
        # content is still being pre-generated, _navigate_to_leaf awaits
        # the in-flight task instead of firing a duplicate LLM call.
        # S8: if a second tab claims the session while pre-gen is running for
        # the first tab, in-flight sse.send_to_session calls silently no-op
        # (return False) because the SSE connection was closed on claim. This
        # is acceptable — the new tab will re-trigger generation on its own
        # navigation.
        self._pregen_leaf_tasks: dict[tuple[str, str], asyncio.Task] = {}

        # All fire-and-forget tasks created via asyncio.create_task. Completed
        # tasks remove themselves via add_done_callback. Used by cleanup() to
        # cancel pending tasks on shutdown.
        self._background_tasks: set[asyncio.Task] = set()

        # Optional callback that records cited position ids for study
        # sessions. Registered by the exploration_study facade at startup.
        # Signature: ``async (chat_id: str, position_ids: list[str]) -> None``.
        self._study_exposure_logger: (
            "Callable[[str, list[str]], Awaitable[None]] | None"
        ) = None

    def set_study_exposure_logger(
        self,
        logger_fn: "Callable[[str, list[str]], Awaitable[None]]",
    ) -> None:
        """
        Register a callback that persists cited position ids for study
        sessions. Called from ``_log_study_exposure`` after the LLM cites
        sources — the callback typically resolves the chat id to a study
        session and merges the ids into ``condition.positions_encountered``.
        """
        self._study_exposure_logger = logger_fn
        logger.info("Study exposure logger registered")

    def _evict_stale_pending_queries(self) -> None:
        """Remove pending queries older than _PENDING_QUERY_TTL_SECONDS.

        Called before every write so abandoned sessions don't cause
        unbounded growth — entries are only deleted on user choice otherwise.
        """
        now = datetime.now(timezone.utc)
        stale = [
            qid
            for qid, pq in self._pending_queries.items()
            if (now - pq.created_at).total_seconds() > _PENDING_QUERY_TTL_SECONDS
        ]
        for qid in stale:
            del self._pending_queries[qid]
        if stale:
            logger.debug(f"Evicted {len(stale)} stale pending queries")

    async def _log_study_exposure(
        self,
        session_id: str,
        citations: list[Citation],
    ) -> None:
        """
        Log cited position ids for the participant if this is a study
        session. Silent no-op for non-study sessions and when no logger
        has been registered. Failures are logged but do not propagate to
        the user-facing response.
        """
        if self._study_exposure_logger is None or not citations:
            return

        session = await self._repo.get_session(session_id)
        if not session or not is_study_context(session.context_id):
            return

        position_ids = [c.id for c in citations if c.id]
        if not position_ids:
            return

        try:
            await self._study_exposure_logger(session_id, position_ids)
        except Exception as e:
            logger.warning(
                f"Study exposure logger failed for session {session_id}: {e}"
            )

    # =========================================================================
    # Context Helpers
    # =========================================================================

    async def _get_context_info(
        self, context_id: str
    ) -> tuple[str, dict[str, PartyInfo]]:
        """
        Get context name and available parties.

        For study contexts (``study-*``), returns static fake-party data
        without touching Firebase. For all other contexts, loads from
        Firebase as before.

        Returns:
            Tuple of (context_name, {party_id: PartyInfo})
        """
        # Check cache first — treat as miss if entry has expired
        cached = self._context_cache.get(context_id)
        if cached is not None:
            ts, context_name, parties_info = cached
            if time.monotonic() - ts < _CONTEXT_CACHE_TTL_SECONDS:
                return context_name, parties_info

        # Study sessions use fictional parties — no Firebase lookup.
        if is_study_context(context_id):
            context_name, parties_info = get_study_context_info(context_id)
            self._context_cache[context_id] = (time.monotonic(), context_name, parties_info)
            return context_name, parties_info

        # Load from Firebase
        context = await aget_context_by_id(context_id)
        context_name = context.name if context else context_id

        parties = await aget_parties_for_context(context_id)
        parties_info = parties_to_info_map(parties)

        # Cache the result with a timestamp
        self._context_cache[context_id] = (time.monotonic(), context_name, parties_info)

        return context_name, parties_info

    async def _get_default_parties(self, context_id: str) -> list[str]:
        """Get default parties for a context."""
        if is_study_context(context_id):
            return list(STUDY_PARTY_IDS)
        _, parties_info = await self._get_context_info(context_id)
        return list(parties_info.keys())

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        context_id: str,
        user_id: str | None = None,
        mode: SessionMode = SessionMode.GUIDED,
    ) -> SessionInfo:
        """Create a new guided exploration session."""
        session = await self._repo.create_session(
            context_id=context_id,
            user_id=user_id,
            mode=mode,
        )

        logger.info(f"Created session: {session.id} with mode={mode.value}")

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

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(
        self,
        session_id: str,
        content: str,
        exploration_context: dict | None = None,
    ) -> dict:
        """
        Handle a user message.

        If no exploration context, classifies query and sends choice prompt.
        If within exploration, handles as followup.
        """
        # Verify session exists
        session = await self._repo.get_session(session_id)
        if not session:
            await self._send_error(
                session_id,
                "session_not_found",
                "Sitzung nicht gefunden",
            )
            return {"status": "error", "code": "session_not_found"}

        # Update activity
        await self._repo.update_session_activity(session_id)

        if exploration_context:
            # Handle as followup within exploration
            return await self.handle_followup(
                session_id,
                exploration_context.get("exploration_id", ""),
                exploration_context.get("leaf_id", ""),
                content,
            )

        # Baseline mode has its own self-contained router (no exploration option).
        # Guided routing below stays untouched.
        if session.mode == SessionMode.BASELINE:
            return await self._handle_baseline_message(
                session_id=session_id,
                session=session,
                content=content,
            )

        # Send thinking event
        await self._send_thinking(
            session_id, "classifying", "Analysiere die Anfrage..."
        )

        # Get context info for classification
        context_name, parties_info = await self._get_context_info(session.context_id)

        # Get recent conversation history for context (back-references like "tell me more")
        conversation_history = self._format_conversation_history(session.messages)

        # Classify the query
        classifier_output = await self._query_classifier.execute(
            QueryClassifierInput(
                query=content,
                context_id=session.context_id,
                context_name=context_name,
                parties_info=parties_info,
                conversation_history=conversation_history,
            )
        )

        # Save user message to session
        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        logger.info(f"Classified message: {classifier_output}")

        # For exploratory queries in guided mode, ask user: quick answer or explore deeper?
        if classifier_output.query_type == QueryType.EXPLORATORY:
            return await self._send_choice_prompt(
                session_id=session_id,
                original_query=content,
                detected_parties=classifier_output.detected_parties,
                rag_query=classifier_output.rag_query,
            )

        # For meta queries — answer about the tool, suggest topics, explain features
        if classifier_output.query_type == QueryType.META:
            return await self._handle_meta_query(
                session_id=session_id,
                query=content,
                session=session,
            )

        # For factual queries, answer directly without exploration
        if classifier_output.query_type == QueryType.FACTUAL:
            return await self._answer_factual_query(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties,
                context_id=session.context_id,
            )

        # For clarification queries, ask for clarification
        if classifier_output.query_type == QueryType.CLARIFICATION:
            clarification_msg = classifier_output.clarification_question or (
                "Könnten Sie Ihre Frage bitte präzisieren?"
            )

            # Stream the clarification request
            stream_id = str(uuid4())
            await self._stream_text(
                session_id,
                clarification_msg,
                stream_id,
                "system_message",
                "system",
            )

            await self._send_chat_message(session_id, message=clarification_msg)

            # Save assistant message
            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=clarification_msg,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "clarification_needed"}

        # Fallback for unknown query types
        fallback_msg = (
            "Ich konnte Ihre Anfrage nicht einordnen. "
            "Bitte stellen Sie eine Frage zu politischen Themen."
        )

        stream_id = str(uuid4())
        await self._stream_text(
            session_id,
            fallback_msg,
            stream_id,
            "system_message",
            "system",
        )

        await self._send_chat_message(session_id, message=fallback_msg)

        return {
            "status": "unknown_query_type",
            "query_type": classifier_output.query_type.value,
        }

    async def _handle_baseline_message(
        self,
        session_id: str,
        session,
        content: str,
    ) -> dict:
        """
        Self-contained router for BASELINE mode.

        No exploration option is offered. Content questions go through the
        conversational quick summary path; meta and clarification queries use
        their existing handlers (also conversational). Guided routing in
        ``handle_message`` is intentionally untouched.
        """
        # Send thinking event
        await self._send_thinking(
            session_id, "classifying", "Analysiere die Anfrage..."
        )

        # Get context info for classification
        context_name, parties_info = await self._get_context_info(session.context_id)

        # Get recent conversation history (back-references like "und bei der CDU?")
        conversation_history = self._format_conversation_history(session.messages)

        # Classify the query
        classifier_output = await self._query_classifier.execute(
            QueryClassifierInput(
                query=content,
                context_id=session.context_id,
                context_name=context_name,
                parties_info=parties_info,
                conversation_history=conversation_history,
            )
        )

        # Save user message to session
        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        logger.info(f"Baseline classified message: {classifier_output}")

        # Content questions → conversational quick summary
        if classifier_output.query_type == QueryType.EXPLORATORY:
            return await self._generate_quick_summary(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties
                or await self._get_default_parties(session.context_id),
                context_id=session.context_id,
                session=session,
            )

        # Specific factual questions → already-conversational factual handler
        if classifier_output.query_type == QueryType.FACTUAL:
            return await self._answer_factual_query(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties,
                context_id=session.context_id,
            )

        # Meta questions about the tool / orientation
        if classifier_output.query_type == QueryType.META:
            return await self._handle_meta_query(
                session_id=session_id,
                query=content,
                session=session,
            )

        # Clarification queries
        if classifier_output.query_type == QueryType.CLARIFICATION:
            clarification_msg = classifier_output.clarification_question or (
                "Könntest du deine Frage bitte präzisieren?"
            )

            stream_id = str(uuid4())
            await self._stream_text(
                session_id,
                clarification_msg,
                stream_id,
                "system_message",
                "system",
            )

            await self._send_chat_message(session_id, message=clarification_msg)

            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=clarification_msg,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "clarification_needed"}

        # Fallback for unknown query types
        fallback_msg = (
            "Ich konnte deine Anfrage nicht einordnen. "
            "Bitte stelle eine Frage zu politischen Themen."
        )

        stream_id = str(uuid4())
        await self._stream_text(
            session_id,
            fallback_msg,
            stream_id,
            "system_message",
            "system",
        )

        await self._send_chat_message(session_id, message=fallback_msg)

        return {
            "status": "unknown_query_type",
            "query_type": classifier_output.query_type.value,
        }

    async def _handle_meta_query(
        self,
        session_id: str,
        query: str,
        session,
    ) -> dict:
        """Handle meta questions about wahl.chat itself (the tool, not topics)."""
        from langchain_core.messages import HumanMessage, SystemMessage

        # Format actual conversation history (last 10 turns) so meta replies
        # can build on prior context rather than starting from scratch.
        history_lines = self._format_conversation_history(session.messages)
        if history_lines:
            conversation_text = "\n".join(history_lines)
        else:
            conversation_text = "Keine vorherigen Nachrichten."

        system_prompt = (
            "Du bist der Assistent von wahl.chat — einem KI-Tool, das es "
            "ermöglicht, sich interaktiv und zeitgemäß über die Positionen und "
            "Pläne der Parteien zu informieren.\n\n"
            "Der Nutzer stellt eine Frage über das Tool selbst (z.B. wie es "
            "funktioniert, was es kann, wer dahinter steht). Antworte "
            "freundlich, kurz und hilfreich auf Deutsch mit korrekten "
            "Umlauten. Spreche den Nutzer mit Du an.\n\n"
            "# So funktioniert wahl.chat\n"
            "- Du kannst zu jedem politischen Thema die Positionen der "
            "Parteien vergleichen — auf Basis ihrer Wahlprogramme.\n"
            "- Wenn Du ein Thema nennst, schlage ich Dir Aspekte zur "
            "Vertiefung vor; Du wählst aus, was Dich interessiert.\n"
            "- Antworten sind quellenbasiert; Du siehst, woher die Aussagen "
            "stammen.\n\n"
            "# Wichtig\n"
            "- Liste hier KEINE Themenvorschläge auf — Themenfragen werden "
            "an anderer Stelle behandelt. Beantworte ausschließlich die "
            "konkrete Tool-Frage.\n"
            "- Bei der Aufforderung, ein Thema zu nennen: lade den Nutzer "
            "kurz ein, einfach ein Thema einzugeben — ohne Liste.\n\n"
            f"# Bisheriges Gespräch\n{conversation_text}\n\n"
            "# Konversationsfluss\n"
            "- Behandle den Austausch als fortlaufendes Gespräch.\n"
            "- Berücksichtige das bisherige Gespräch und vermeide Wiederholungen.\n"
            "- Keine Begrüßung mitten im Gespräch."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        # Use fast LLM for quick response
        llm = self._llm_registry.get(LLMTier.FAST)

        # Stream the response
        stream_id = str(uuid4())
        full_text = await self._stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=llm.stream(messages=messages, temperature=0.7),
            target_type="quick_summary",
            target_id="meta",
        )

        await self._send_chat_message(session_id, full_text)

        assistant_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.ASSISTANT,
            content=full_text,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)

        return {"status": "meta_answered"}

    async def _send_choice_prompt(
        self,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
    ) -> dict:
        """Send choice prompt and track pending query."""
        query_id = str(uuid4())

        # Evict stale entries before adding a new one (S4)
        self._evict_stale_pending_queries()

        # Track pending query
        self._pending_queries[query_id] = PendingQuery(
            query_id=query_id,
            session_id=session_id,
            original_query=original_query,
            detected_parties=detected_parties,
            rag_query=rag_query,
        )

        # Send thinking for planning
        await self._send_thinking(
            session_id, "planning", "Identifiziere relevante Themen..."
        )

        options = [
            {
                "id": "summary",
                "label": "Schnelle Antwort",
                "description": "Kompakte Übersicht der Parteipositionen",
            },
            {
                "id": "explore",
                "label": "Thema vertiefen",
                "description": "Aspekte auswählen und Positionen im Detail vergleichen",
            },
        ]

        # Persist a research-only audit message so the study admin can see
        # the participant was offered the explore-vs-summary choice. The
        # chat frontend filters CHOICE_PROMPT messages out.
        choice_prompt_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.CHOICE_PROMPT,
            query_id=query_id,
            original_query=original_query,
            options=options,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, choice_prompt_msg)

        # Send choice prompt event
        await self._sse.send_to_session(
            session_id,
            ChoicePromptEvent(
                query_id=query_id,
                original_query=original_query,
                options=options,
            ),
        )

        logger.info(
            f"Sent choice prompt for session {session_id}, query_id: {query_id}"
        )

        return {
            "status": "pending_choice",
            "query_id": query_id,
            "detected_parties": detected_parties,
            "rag_query": rag_query,
        }

    async def _send_topic_directions(
        self,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
        context_id: str,
    ) -> dict:
        """Scout topic directions and send them for user selection."""
        query_id = str(uuid4())

        # Determine parties
        if not detected_parties:
            detected_parties = await self._get_default_parties(context_id)

        # Check cache first — exact match on original query
        cache_key = (original_query, context_id)
        _cached_directions = self._directions_cache.get(cache_key)
        if _cached_directions is not None:
            _ts, _val = _cached_directions
            if time.monotonic() - _ts >= _DIRECTIONS_CACHE_TTL_SECONDS:
                _cached_directions = None  # expired — treat as miss

        if _cached_directions is not None:
            logger.info(f"Cache hit for topic directions: '{original_query}'")
            scout_output = _cached_directions[1]
        else:
            # Send thinking event (only when not cached)
            await self._send_thinking(
                session_id, "retrieving", "Suche relevante Themenrichtungen..."
            )

            # Quick RAG retrieval to scout directions
            chunks = await self._retrieve_chunks_for_summary(
                rag_query, context_id, detected_parties
            )

            if not chunks:
                # No data found — tell the user, don't loop back to choice
                no_data_msg = (
                    "Zu diesem Thema habe ich leider keine passenden "
                    "Informationen in den Wahlprogrammen gefunden. "
                    "Versuche es mit einem konkreteren Thema oder einer "
                    "anderen Formulierung."
                )
                stream_id = str(uuid4())
                await self._stream_text(
                    session_id, no_data_msg, stream_id,
                    "quick_summary", "system",
                )
                await self._send_chat_message(session_id, no_data_msg)
                assistant_msg = SessionMessage(
                    id=str(uuid4()),
                    type=SessionMessageType.ASSISTANT,
                    content=no_data_msg,
                    timestamp=datetime.now(timezone.utc),
                )
                await self._repo.add_session_message(session_id, assistant_msg)
                return {"status": "no_data"}

            # Get context info
            context_name, parties_info = await self._get_context_info(context_id)

            # Format chunks for the scout
            parties_map = {
                p_id: parties_info.get(p_id) for p_id in detected_parties
            }
            chunks_text = self._format_chunks_for_scout(chunks, parties_map)

            # Run topic scout agent
            scout_output = await self._topic_scout.execute(
                TopicScoutInput(
                    query=original_query,
                    rag_chunks_text=chunks_text,
                    parties_info=parties_info,
                    context_name=context_name,
                )
            )

            # Cache if the LLM flagged this as reusable (with timestamp)
            if scout_output.cacheable:
                self._directions_cache[cache_key] = (time.monotonic(), scout_output)
                logger.info(
                    f"Cached topic directions for: '{original_query}'"
                )

        # Evict stale entries before adding a new one (S4)
        self._evict_stale_pending_queries()

        # Track pending query
        self._pending_queries[query_id] = PendingQuery(
            query_id=query_id,
            session_id=session_id,
            original_query=original_query,
            detected_parties=detected_parties,
            rag_query=rag_query,
        )

        # Save directions as a structured session message for persistence
        directions_data = [
            {
                "id": d.id,
                "name": d.name,
                "hook": d.hook,
                "suggested_question": d.suggested_question,
            }
            for d in scout_output.directions
        ]
        directions_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.TOPIC_DIRECTIONS,
            content=None,
            directions=directions_data,
            directions_query_id=query_id,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, directions_msg)

        # Send topic directions event (renders interactive cards via SSE)
        # The frontend SSE handler ends thinking when it receives this event
        delivered = await self._sse.send_to_session(
            session_id,
            TopicDirectionsEvent(
                query_id=query_id,
                original_query=original_query,
                directions=[
                    TopicDirectionItem(
                        id=d.id,
                        name=d.name,
                        hook=d.hook,
                        suggested_question=d.suggested_question,
                    )
                    for d in scout_output.directions
                ],
            ),
        )

        logger.info(
            f"Sent {len(scout_output.directions)} topic directions "
            f"for session {session_id}, query_id: {query_id}, "
            f"SSE delivered: {delivered}"
        )

        return {
            "status": "pending_direction",
            "query_id": query_id,
            "directions_count": len(scout_output.directions),
        }

    def _format_chunks_for_scout(
        self,
        chunks: list[RetrievedChunk],
        parties_map: dict,
    ) -> str:
        """Format RAG chunks for the topic scout prompt."""
        chunks_by_party: dict[str, list[RetrievedChunk]] = {}
        for chunk in chunks:
            if chunk.party_id not in chunks_by_party:
                chunks_by_party[chunk.party_id] = []
            chunks_by_party[chunk.party_id].append(chunk)

        parts = []
        for party_id, party_chunks in chunks_by_party.items():
            party = parties_map.get(party_id)
            party_name = party.name if party else party_id.upper()
            parts.append(f"\n## {party_name}")
            for chunk in party_chunks:
                parts.append(f"- {chunk.content[:400]}")
        return "\n".join(parts)

    async def handle_direction_choice(
        self,
        session_id: str,
        query_id: str,
        directions: list[dict],
    ) -> dict:
        """Handle user's topic direction choices — start focused exploration."""
        pending = self._pending_queries.get(query_id)
        if not pending:
            await self._send_error(
                session_id,
                "query_not_found",
                "Anfrage nicht gefunden oder bereits bearbeitet",
            )
            return {"status": "error", "code": "query_not_found"}

        if pending.session_id != session_id:
            await self._send_error(
                session_id,
                "session_mismatch",
                "Anfrage gehört zu einer anderen Sitzung",
            )
            return {"status": "error", "code": "session_mismatch"}

        # Remove from pending
        del self._pending_queries[query_id]

        # Get session for context_id
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Persist the user's selection on the original topic_directions message
        direction_names = [d["name"] for d in directions]

        # Find the topic_directions message by query_id and update it
        session_messages = await self._repo.get_session_messages(session_id)
        for msg in session_messages:
            if (
                msg.type == SessionMessageType.TOPIC_DIRECTIONS
                and msg.directions_query_id == query_id
            ):
                await self._repo.update_session_message(
                    session_id,
                    msg.id,
                    {"selected_directions": direction_names},
                )
                break

        # Build focused query from selected directions
        if len(direction_names) >= 5:
            # All directions selected — no focus suffix
            focused_query = pending.original_query
        else:
            focus = ", ".join(direction_names)
            focused_query = f"{pending.original_query} — Fokus: {focus}"

        # Combine direction names for broader RAG retrieval
        rag_focus = " ".join(direction_names)

        # Determine parties
        exploration_parties = (
            pending.detected_parties
            or await self._get_default_parties(session.context_id)
        )

        return await self._start_exploration_internal(
            session_id=session_id,
            query=focused_query,
            rag_query=f"{pending.rag_query} {rag_focus}",
            context_id=session.context_id,
            parties=exploration_parties,
            selected_directions=direction_names,
        )

    async def handle_choice(
        self,
        session_id: str,
        query_id: str,
        choice: Literal["explore", "summary"],
        parties: list[str] | None = None,
    ) -> dict:
        """Handle user's choice for explore vs summary."""
        # Verify pending query
        pending = self._pending_queries.get(query_id)
        if not pending:
            await self._send_error(
                session_id,
                "query_not_found",
                "Anfrage nicht gefunden oder bereits bearbeitet",
            )
            return {"status": "error", "code": "query_not_found"}

        if pending.session_id != session_id:
            await self._send_error(
                session_id,
                "session_mismatch",
                "Anfrage gehört zu einer anderen Sitzung",
            )
            return {"status": "error", "code": "session_mismatch"}

        # Remove from pending
        del self._pending_queries[query_id]

        # Persist a research-only audit message recording the user's pick.
        # The chat frontend filters CHOICE_MADE messages out.
        choice_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.CHOICE_MADE,
            query_id=query_id,
            choice=choice,
            original_query=pending.original_query,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, choice_msg)

        # Get session for context_id
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Determine parties to use
        if parties:
            exploration_parties = parties
        elif pending.detected_parties:
            exploration_parties = pending.detected_parties
        else:
            exploration_parties = await self._get_default_parties(session.context_id)

        if choice == "explore":
            # User wants to explore deeper — show topic directions
            return await self._send_topic_directions(
                session_id=session_id,
                original_query=pending.original_query,
                detected_parties=exploration_parties,
                rag_query=pending.rag_query,
                context_id=session.context_id,
            )
        else:
            # Generate quick summary without exploration (with conversation history)
            return await self._generate_quick_summary(
                session_id=session_id,
                query=pending.original_query,
                rag_query=pending.rag_query,
                detected_parties=exploration_parties,
                context_id=session.context_id,
                session=session,
            )

    # =========================================================================
    # Exploration Start
    # =========================================================================

    async def _start_exploration_internal(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
        rag_query: str | None = None,
        selected_directions: list[str] | None = None,
    ) -> dict:
        """Internal method to start exploration (called after choice)."""
        try:
            # Send initial message to inform user we're working on it
            await self._sse.send_to_session(
                session_id,
                ChatMessageEvent(
                    message_id=str(uuid4()),
                    content=(
                        "Perfekt! Ich suche jetzt Informationen zu diesem Thema und "
                        "melde mich, sobald ich fertig bin. Du kannst den Fortschritt "
                        "hier im Chat verfolgen."
                    ),
                ),
            )

            # Run orchestrator (sends SSE events including TopicTreeEvent)
            (
                exploration_id,
                exploration_tree,
                low_confidence,
            ) = await self._orchestrator.start_exploration(
                session_id=session_id,
                query=query,
                rag_query=rag_query or query,
                context_id=context_id,
                parties=parties,
            )

            # Attach selected directions to the tree for context display
            if selected_directions:
                exploration_tree.selected_directions = selected_directions

            # Send and persist caveat message if data is limited
            if low_confidence:
                caveat_text = (
                    "Zu diesem Thema habe ich nur begrenzte Informationen "
                    "gefunden. Die Erkundung zeigt die verfügbaren "
                    "Positionen — es kann sein, dass nicht alle Parteien "
                    "vertreten sind."
                )
                await self._send_chat_message(session_id, message=caveat_text)
                caveat_msg = SessionMessage(
                    id=str(uuid4()),
                    type=SessionMessageType.ASSISTANT,
                    content=caveat_text,
                    timestamp=datetime.now(timezone.utc),
                )
                await self._repo.add_session_message(session_id, caveat_msg)

            # Persist exploration
            await self._repo.create_exploration(
                session_id,
                query,
                tree=exploration_tree,
                exploration_id=exploration_id,
            )

            # Add exploration reference to session messages
            exploration_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.EXPLORATION_START,
                content=None,
                exploration_id=exploration_id,
                exploration_query=query,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, exploration_msg)

            # Study sessions: eagerly pre-generate all leaf content in the
            # background so participants never wait when they open a leaf.
            # Non-study flows keep the lazy-on-open behavior.
            if is_study_context(context_id):
                context_name, parties_info = await self._get_context_info(
                    context_id
                )
                _pregen_task = asyncio.create_task(
                    self._pregen_study_leaves(
                        session_id=session_id,
                        exploration_id=exploration_id,
                        tree=exploration_tree,
                        context_name=context_name,
                        parties_info=parties_info,
                    )
                )
                self._background_tasks.add(_pregen_task)
                _pregen_task.add_done_callback(self._background_tasks.discard)

            # Initialize navigation state at root
            self._navigation_states[session_id] = NavigationState(
                exploration_id=exploration_id,
                current_path=[],
                breadcrumb=[
                    BreadcrumbItem(
                        id="root",
                        name="Übersicht",
                        level=BreadcrumbLevel.ROOT,
                    ),
                ],
            )

            return {
                "status": "exploration_started",
                "exploration_id": exploration_id,
            }

        except InsufficientChunksError as e:
            logger.warning(
                f"Insufficient data for exploration: {e.parties_with_chunks}/"
                f"{e.total_parties} parties have data. "
                f"Missing: {', '.join(e.parties_without_chunks)}"
            )

            # Friendly message — no raw data dump
            chat_message = (
                "Zu diesem Thema habe ich leider zu wenige Informationen "
                "in den Wahlprogrammen gefunden, um eine Erkundung zu starten. "
                "Versuche es mit einer anderen Frage oder formuliere das "
                "Thema etwas breiter."
            )

            # Stream the message
            stream_id = str(uuid4())
            await self._stream_text(
                session_id,
                chat_message,
                stream_id,
                "quick_summary",
                "system",
            )

            # Send chat message event
            await self._send_chat_message(session_id, chat_message)

            # Save assistant message
            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=chat_message,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "insufficient_data"}

        except Exception as e:
            logger.error(f"Failed to start exploration: {e}")
            await self._send_error(
                session_id,
                "exploration_failed",
                "Fehler beim Starten der Erkundung",
            )
            return {"status": "error", "code": "exploration_failed"}

    async def start_exploration(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
    ) -> dict:
        """
        Start a new exploration directly (bypasses choice flow).

        For normal flow, use handle_message -> handle_choice instead.
        """
        # Verify session exists
        session = await self._repo.get_session(session_id)
        if not session:
            await self._send_error(
                session_id,
                "session_not_found",
                "Sitzung nicht gefunden",
            )
            return {"status": "error", "code": "session_not_found"}

        # Update activity
        await self._repo.update_session_activity(session_id)

        # Save user message to session
        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=query,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        return await self._start_exploration_internal(
            session_id=session_id,
            query=query,
            context_id=context_id,
            parties=parties,
        )

    # =========================================================================
    # Navigation
    # =========================================================================

    async def navigate(
        self,
        session_id: str,
        exploration_id: str,
        target_path: list[str],
    ) -> dict:
        """Navigate within the topic tree."""
        # Get session for context
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Get exploration
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        tree = exploration.tree

        if len(target_path) == 0:
            # Navigate to root
            self._navigation_states[session_id] = NavigationState(
                exploration_id=exploration_id,
                current_path=[],
                breadcrumb=[
                    BreadcrumbItem(
                        id="root",
                        name="Übersicht",
                        level=BreadcrumbLevel.ROOT,
                    ),
                ],
            )
            return {"status": "at_root"}

        # Find the target node by the last element of the path
        target_id = target_path[-1]
        node = tree.find_node(target_id)
        if not node:
            await self._send_error(
                session_id,
                "node_not_found",
                f"Knoten '{target_id}' nicht gefunden",
            )
            return {"status": "error", "code": "node_not_found"}

        if node.is_leaf:
            # Leaf node — generate content
            context_name, parties_info = await self._get_context_info(
                session.context_id
            )

            conversation, navigation = await self._navigate_to_leaf(
                session_id,
                exploration,
                leaf_id=node.id,
                leaf_name=node.name,
                leaf_parties=node.party_ids,
                context_name=context_name,
                parties_info=parties_info,
            )

            await self._repo.save_conversation(
                session_id,
                exploration_id,
                conversation,
            )

            self._navigation_states[session_id] = navigation
            return {"status": "navigated", "path": target_path}

        else:
            # Branch node — show overview
            navigation = await self._navigate_to_branch(
                session_id,
                exploration,
                node,
            )
            self._navigation_states[session_id] = navigation
            return {"status": "navigated", "path": target_path}

    async def mark_explored(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        """
        Mark a leaf as explored and generate a summary.

        Called explicitly by the frontend when user has engaged with content.
        Generates a leaf summary based on the conversation.
        """
        # Get session for context
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Get exploration
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        tree = exploration.tree

        # Mark as explored
        await self._mark_leaf_explored(
            session_id,
            exploration_id,
            leaf_id,
            tree,
        )

        # Generate leaf summary
        try:
            # Get conversation for this leaf
            conversation = await self._repo.get_conversation(
                session_id, exploration_id, leaf_id
            )

            if conversation and conversation.messages:
                # Get subtopic content from first message
                first_msg = conversation.messages[0]
                if hasattr(first_msg.content, "summary"):
                    subtopic_content = first_msg.content

                    # Get context info
                    context_name, _ = await self._get_context_info(session.context_id)

                    # Find leaf name
                    leaf_name = self._get_leaf_name(tree, leaf_id)

                    # Send summary generating event
                    await self._sse.send_to_session(
                        session_id,
                        SummaryGeneratingEvent(
                            leaf_id=leaf_id,
                            status="started",
                        ),
                    )

                    # Generate summary
                    leaf_summary = await self._summary_generator.execute(
                        LeafSummaryInput(
                            leaf_id=leaf_id,
                            leaf_name=leaf_name,
                            conversation=conversation,
                            subtopic_content=subtopic_content,
                            context_name=context_name,
                        )
                    )

                    # Save summary
                    await self._repo.save_leaf_summary(
                        session_id,
                        exploration_id,
                        LeafSummary.model_validate(leaf_summary),
                    )

                    # Send summary completed event
                    await self._sse.send_to_session(
                        session_id,
                        SummaryGeneratingEvent(
                            leaf_id=leaf_id,
                            status="completed",
                        ),
                    )

                    logger.debug(f"Generated summary for leaf {leaf_id}")

        except Exception as e:
            logger.error(f"Failed to generate leaf summary: {e}")
            # Don't fail the mark_explored - just log the error
            await self._sse.send_to_session(
                session_id,
                SummaryGeneratingEvent(
                    leaf_id=leaf_id,
                    status="failed",
                    error=str(e),
                ),
            )

        return {"status": "marked_explored", "leaf_id": leaf_id}

    def _get_leaf_name(self, tree: ExplorationTree, leaf_id: str) -> str:
        """Get the display name for a leaf node."""
        node = tree.find_node(leaf_id)
        if node is not None:
            return node.name
        return leaf_id

    async def _navigate_to_branch(
        self,
        session_id: str,
        exploration: Exploration,
        node: ExplorationNode,
    ) -> NavigationState:
        """Navigate to a branch node."""
        # Build breadcrumb from path
        path = exploration.tree.root.get_path_to(node.id) or []
        breadcrumb = [
            BreadcrumbItem(
                id="root",
                name="Übersicht",
                level=BreadcrumbLevel.ROOT,
            ),
        ]
        for p in path[1:]:  # skip root
            breadcrumb.append(
                BreadcrumbItem(
                    id=p.id,
                    name=p.name,
                    level=BreadcrumbLevel.TOPIC if not p.is_leaf else BreadcrumbLevel.SUBTOPIC,
                ),
            )

        navigation = NavigationState(
            exploration_id=exploration.id,
            current_path=[n.id for n in path[1:]],
            breadcrumb=breadcrumb,
        )

        await self._sse.send_to_session(
            session_id,
            TopicOverviewEvent(
                topic_id=node.id,
                name=node.name,
                description=node.description,
                children=node.children,
                navigation=navigation,
            ),
        )

        return navigation

    async def _navigate_to_leaf(
        self,
        session_id: str,
        exploration: Exploration,
        leaf_id: str,
        leaf_name: str,
        leaf_parties: list[str],
        context_name: str = "",
        parties_info: dict[str, PartyInfo] | None = None,
    ) -> tuple[Conversation, NavigationState]:
        """Navigate to a leaf node and generate content."""
        if parties_info is None:
            parties_info = {}

        # B2: Check the pre-gen registry FIRST to avoid a race where the task
        # completes and the finally-pop removes the key between get_conversation
        # and the registry check — which would cause a duplicate LLM call.
        pregen_task = self._pregen_leaf_tasks.get((exploration.id, leaf_id))
        if pregen_task is not None:
            if not pregen_task.done():
                # Task still in flight — show a spinner and await it.
                await self._send_thinking(
                    session_id, "generating", "Bereite Inhalte vor..."
                )
            try:
                await pregen_task  # awaiting a done task returns immediately
            except Exception:
                logger.warning(
                    "pregen task failed for leaf %s, falling back to lazy path",
                    leaf_id,
                    exc_info=True,
                )

        # Now fetch the conversation exactly once — benefits from any
        # content that pregen may have just persisted.
        existing_conversation = await self._repo.get_conversation(
            session_id, exploration.id, leaf_id
        )

        # Get positions for this leaf from the exploration tree
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)

        # Build navigation from tree path
        node_path = exploration.tree.root.get_path_to(leaf_id) or []
        current_path = [n.id for n in node_path[1:]]  # skip root
        breadcrumb = [
            BreadcrumbItem(
                id="root",
                name="Übersicht",
                level=BreadcrumbLevel.ROOT,
            ),
        ]
        for n in node_path[1:]:
            breadcrumb.append(
                BreadcrumbItem(
                    id=n.id,
                    name=n.name,
                    level=BreadcrumbLevel.SUBTOPIC if n.is_leaf else BreadcrumbLevel.TOPIC,
                ),
            )

        navigation = NavigationState(
            exploration_id=exploration.id,
            current_path=current_path,
            breadcrumb=breadcrumb,
        )

        # Initialize content variable
        content = None

        # Use existing conversation if available (cached content)
        if existing_conversation and existing_conversation.messages:
            conversation = existing_conversation

            # Get cached content from first message
            initial_msg = existing_conversation.messages[0]
            if hasattr(initial_msg.content, "summary"):
                content = initial_msg.content
                # Cached content is delivered via ConversationOpenedEvent below,
                # so no re-streaming is needed. Streaming the summary again would
                # leave a stale buffer on the client that renders a duplicate
                # summary below the already-committed structured message.
        else:
            # Generate new content
            await self._send_thinking(
                session_id, "generating", "Bereite Inhalte vor..."
            )

            # Build path for content generator
            path = current_path

            leaf_citations = collect_leaf_citations(positions_by_party)
            content = await self._content_generator.execute(
                ContentGeneratorInput(
                    subtopic_id=leaf_id,
                    subtopic_name=leaf_name,
                    path=path,
                    leaf_positions=positions_by_party,
                    leaf_citations=leaf_citations,
                    context_id=exploration.tree.exploration_id,
                    context_name=context_name,
                    parties_info=parties_info,
                    parties=leaf_parties,
                )
            )

            # Stream the summary
            stream_id = str(uuid4())
            await self._stream_text(
                session_id,
                content.summary,
                stream_id,
                "initial_content",
                leaf_id,
                section="summary",
            )

            # Create conversation with initial content
            now = datetime.now(timezone.utc)
            initial_message = Message(
                id=str(uuid4()),
                role=MessageRole.ASSISTANT,
                type=MessageType.INITIAL_CONTENT,
                content=content,
                timestamp=now,
            )

            conversation = Conversation(
                leaf_id=leaf_id,
                messages=[initial_message],
                has_summary=False,
            )

            # Save conversation to Firebase
            await self._repo.save_conversation(
                session_id,
                exploration.id,
                conversation,
            )

        # Promote node status to 'started' unless the user already finished it.
        # Transitions: pending/loaded -> started. 'explored' is terminal.
        leaf_node = exploration.tree.find_node(leaf_id)
        if leaf_node is not None and leaf_node.status in {NodeStatus.PENDING, NodeStatus.LOADED}:
            leaf_node.status = NodeStatus.STARTED
            try:
                await self._repo.update_tree(
                    session_id, exploration.id, exploration.tree
                )
            except Exception as _e:
                # In-memory mutation already done; the next update_tree will
                # heal the discrepancy — do not roll back (S2).
                logger.warning(
                    "update_tree failed after status→started for leaf %s "
                    "(session=%s exploration=%s): %s",
                    leaf_id, session_id, exploration.id, _e,
                )

        # Calculate sibling navigation from parent's children
        previous_sibling = None
        next_sibling = None

        if len(node_path) >= 2:
            parent = node_path[-2]
            sibling_index = next(
                (i for i, c in enumerate(parent.children) if c.id == leaf_id),
                0,
            )
            if sibling_index > 0:
                prev_node = parent.children[sibling_index - 1]
                previous_sibling = BreadcrumbItem(
                    id=prev_node.id,
                    name=prev_node.name,
                    level=BreadcrumbLevel.SUBTOPIC,
                )
            if sibling_index < len(parent.children) - 1:
                next_node = parent.children[sibling_index + 1]
                next_sibling = BreadcrumbItem(
                    id=next_node.id,
                    name=next_node.name,
                    level=BreadcrumbLevel.SUBTOPIC,
                )

        # Extract suggested questions from content (if available)
        suggested_questions: list[str] = []
        if content and hasattr(content, "suggested_questions"):
            suggested_questions = content.suggested_questions or []

        # Send conversation opened event
        await self._sse.send_to_session(
            session_id,
            ConversationOpenedEvent(
                leaf_id=leaf_id,
                conversation=conversation,
                navigation=navigation,
                analysis_available=True,
                sibling_navigation=SiblingNavigation(
                    previous=previous_sibling,
                    next=next_sibling,
                ),
                suggested_questions=suggested_questions,
            ),
        )

        return conversation, navigation

    # =========================================================================
    # Followup Messages
    # =========================================================================

    async def handle_followup(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
        user_message: str,
    ) -> dict:
        """Handle a user message within an active exploration."""
        # Get exploration
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        # Get session for context
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Get context info for classification and content generation
        context_name, parties_info = await self._get_context_info(session.context_id)

        # Get conversation history for context (resolves back-references)
        conversation = await self._repo.get_conversation(
            session_id, exploration_id, leaf_id
        )
        conversation_history = self._format_leaf_conversation_history(conversation)
        last_assistant_message = self._extract_last_assistant_message(conversation)

        # Send thinking event for classification
        await self._send_thinking(
            session_id, "classifying", "Analysiere Ihre Nachricht..."
        )

        # Classify the message intent
        classification = await self._message_classifier.execute(
            MessageClassifierInput(
                message=user_message,
                context_name=context_name,
                current_leaf_id=leaf_id,
                exploration_id=exploration_id,
                conversation_history=conversation_history,
                last_assistant_message=last_assistant_message,
            )
        )

        # Route based on intent
        if classification.intent == MessageIntent.NAVIGATION_COMMAND:
            return await self._handle_navigation_command(
                session_id=session_id,
                exploration_id=exploration_id,
                exploration=exploration,
                current_leaf_id=leaf_id,
                navigation_target=classification.navigation_target,
            )

        logger.info(
            f"Message classified as {classification.intent.value} "
            f"(confidence: {classification.confidence:.2f})"
        )

        # ANALYSIS_REQUEST and SUMMARY_REQUEST go through the conversation
        # handler so both sides of the exchange are persisted and the next
        # follow-up has the full conversation context.
        if classification.intent != MessageIntent.FOLLOWUP_QUESTION:
            return await self._handle_conversation_message(
                session_id=session_id,
                exploration_id=exploration_id,
                exploration=exploration,
                leaf_id=leaf_id,
                user_message=user_message,
                message_type=classification.intent,
                context_name=context_name,
                parties_info=parties_info,
                conversation=conversation,
            )

        # For FOLLOWUP_QUESTION: route through the followup router
        return await self._route_followup(
            session_id=session_id,
            exploration_id=exploration_id,
            exploration=exploration,
            leaf_id=leaf_id,
            user_message=user_message,
            context_name=context_name,
            parties_info=parties_info,
            conversation=conversation,
        )

    async def _handle_navigation_command(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        current_leaf_id: str,
        navigation_target: NavigationTarget | None,
    ) -> dict:
        """Handle a navigation command within an exploration."""
        from src.guided_exploration.models.classification import NavigationTarget

        tree = exploration.tree

        # Get current position
        current_path = self._navigation_states.get(session_id)
        if current_path:
            current_path_list = current_path.current_path
        else:
            current_path_list = []

        # Compute target path based on navigation target
        target_path: list[str] = []

        if navigation_target == NavigationTarget.OVERVIEW:
            target_path = []  # Root

        elif navigation_target == NavigationTarget.BACK:
            # Go up one level
            if len(current_path_list) > 1:
                target_path = current_path_list[:-1]
            else:
                target_path = []  # Back to root

        elif navigation_target in (NavigationTarget.NEXT, NavigationTarget.PREVIOUS):
            # Navigate to sibling node using tree path
            if current_leaf_id:
                node_path = tree.root.get_path_to(current_leaf_id)
                if node_path and len(node_path) >= 2:
                    parent = node_path[-2]
                    sibling_ids = [c.id for c in parent.children]
                    try:
                        current_index = sibling_ids.index(current_leaf_id)
                        new_index = (
                            current_index + 1
                            if navigation_target == NavigationTarget.NEXT
                            else current_index - 1
                        )

                        if 0 <= new_index < len(sibling_ids):
                            target_path = [sibling_ids[new_index]]
                        else:
                            await self._send_error(
                                session_id,
                                "navigation_boundary",
                                "Sie sind bereits am Ende dieses Themenbereichs.",
                                recoverable=True,
                            )
                            return {"status": "at_boundary"}
                    except ValueError:
                        target_path = current_path_list
                else:
                    target_path = current_path_list
            else:
                await self._send_error(
                    session_id,
                    "navigation_not_applicable",
                    "Navigation nicht möglich. Wählen Sie zuerst ein Unterthema.",
                    recoverable=True,
                )
                return {"status": "not_applicable"}

        return await self.navigate(session_id, exploration_id, target_path)

    async def _route_followup(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        leaf_id: str,
        user_message: str,
        context_name: str,
        parties_info: dict[str, PartyInfo],
        conversation: Conversation | None = None,
    ) -> dict:
        """Route a follow-up question through the routing agent."""
        from src.guided_exploration.agents.followup_router import (
            FollowupRouterInput,
            FollowupRoute,
            LeafInfo,
        )
        from src.guided_exploration.agents.followup_router.prompts import (
            format_positions_for_routing,
        )
        from src.guided_exploration.models.events import TopicSwitchSuggestedEvent

        # Gather routing context
        leaf_node = exploration.tree.find_node(leaf_id)
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)

        # Get all other leaves for topic matching
        all_leaves = exploration.tree.root.get_leaf_nodes()
        other_leaves = [
            LeafInfo(id=l.id, name=l.name, description=l.description)
            for l in all_leaves
            if l.id != leaf_id
        ]

        # Run the router
        router_result = await self._followup_router.execute(
            FollowupRouterInput(
                message=user_message,
                leaf_id=leaf_id,
                leaf_name=leaf_node.name if leaf_node else leaf_id,
                leaf_description=leaf_node.description if leaf_node else "",
                existing_positions_summary=format_positions_for_routing(positions_by_party),
                other_leaves=other_leaves,
                context_name=context_name,
            )
        )

        # Route: ON_TOPIC_EXISTING — answer from existing positions
        if router_result.route == FollowupRoute.ON_TOPIC_EXISTING:
            return await self._handle_conversation_message(
                session_id=session_id,
                exploration_id=exploration_id,
                exploration=exploration,
                leaf_id=leaf_id,
                user_message=user_message,
                message_type=MessageIntent.FOLLOWUP_QUESTION,
                context_name=context_name,
                parties_info=parties_info,
                conversation=conversation,
            )

        # Route: ON_TOPIC_NEEDS_RAG — do targeted RAG, then answer
        if router_result.route == FollowupRoute.ON_TOPIC_NEEDS_RAG:
            return await self._handle_followup_with_rag(
                session_id=session_id,
                exploration_id=exploration_id,
                exploration=exploration,
                leaf_id=leaf_id,
                user_message=user_message,
                context_name=context_name,
                parties_info=parties_info,
                conversation=conversation,
                positions_by_party=positions_by_party,
                rag_query=router_result.rag_query,
            )

        # Route: RELATED_TOPIC — suggest switching
        if (
            router_result.route == FollowupRoute.RELATED_TOPIC
            and router_result.target_node_id
        ):
            target_node = exploration.tree.find_node(router_result.target_node_id)
            target_name = (
                target_node.name
                if target_node
                else (router_result.target_node_name or router_result.target_node_id)
            )

            # Send the switch suggestion event
            await self._sse.send_to_session(
                session_id,
                TopicSwitchSuggestedEvent(
                    leaf_id=leaf_id,
                    target_node_id=router_result.target_node_id,
                    target_node_name=target_name,
                    message=(
                        f"Deine Frage passt besser zum Thema \"{target_name}\". "
                        f"Möchtest du dorthin wechseln?"
                    ),
                ),
            )

            # Still answer best-effort from current positions
            return await self._handle_conversation_message(
                session_id=session_id,
                exploration_id=exploration_id,
                exploration=exploration,
                leaf_id=leaf_id,
                user_message=user_message,
                message_type=MessageIntent.FOLLOWUP_QUESTION,
                context_name=context_name,
                parties_info=parties_info,
                conversation=conversation,
            )

        # Route: OFF_TOPIC — polite redirect
        await self._send_thinking(session_id, "generating", "")

        # Add user message to conversation
        now = datetime.now(timezone.utc)
        user_msg = Message(
            id=str(uuid4()),
            role=MessageRole.USER,
            type=MessageType.FOLLOWUP,
            content=user_message,
            timestamp=now,
        )
        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, user_msg
        )
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=user_msg,
            ),
        )

        # Send redirect message
        redirect_msg = Message(
            id=str(uuid4()),
            role=MessageRole.ASSISTANT,
            type=MessageType.FOLLOWUP,
            content=(
                "Diese Frage liegt außerhalb der verfügbaren Themen. "
                "Du kannst über die Navigation ein anderes Thema auswählen "
                "oder dieses Thema abschliessen."
            ),
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, redirect_msg
        )
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=redirect_msg,
            ),
        )
        await self._sse.send_to_session(
            session_id,
            ThinkingEvent(stage="generating", message=""),
        )

        return {"status": "off_topic"}

    async def _handle_followup_with_rag(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        leaf_id: str,
        user_message: str,
        context_name: str,
        parties_info: dict[str, PartyInfo],
        conversation: Conversation | None,
        positions_by_party: dict[str, list],
        rag_query: str | None = None,
    ) -> dict:
        """Handle a follow-up that needs additional RAG retrieval."""
        # Get session for context_id
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        await self._send_thinking(
            session_id, "retrieving", "Suche weitere Details..."
        )

        # Use optimized RAG query if available, otherwise fall back to user message
        search_query = rag_query or user_message

        # Retrieve additional chunks for each party in the leaf
        party_ids = list(positions_by_party.keys())
        import asyncio

        async def retrieve_for_party(party_id: str):
            return party_id, await self._rag_service.retrieve_chunks_for_party(
                query=search_query,
                context_id=session.context_id,
                party_id=party_id,
                n_docs=5,
                score_threshold=0.5,
            )

        results = await asyncio.gather(
            *[retrieve_for_party(pid) for pid in party_ids],
            return_exceptions=True,
        )

        # Build augmented ResolvedKnowledge with existing positions + new chunks
        party_positions: dict[str, ExtractedPosition] = {}
        citation_pool: list[Citation] = []
        party_chunks: dict[str, list] = {}

        # Add existing positions
        for party_id, positions in positions_by_party.items():
            extracted_positions = [
                ExtractedPositionItem(
                    position=c.content,
                    quote=c.quote,
                    source_doc=c.citation.document if c.citation else "",
                    source_page=c.citation.page if c.citation else None,
                    position_type=c.position_type,
                    citation_id=c.citation.id if c.citation else None,
                )
                for c in positions
            ]
            party_positions[party_id] = ExtractedPosition(
                party_id=party_id,
                positions=extracted_positions,
            )
            for c in positions:
                if c.citation is not None:
                    citation_pool.append(c.citation)

        # Add RAG chunks and create citations for them. Citation ids use
        # ``chunk.chunk_id`` so they match the IDs shown to the LLM in
        # ``_build_source_text`` and map directly back to the original
        # chunk (including master position ids for study sessions).
        for result in results:
            if isinstance(result, BaseException):
                continue
            party_id, chunks = result
            party_chunks[party_id] = chunks
            party_name = parties_info.get(
                party_id,
                PartyInfo(
                    party_id=party_id, name=party_id.upper(),
                    long_name=party_id.upper(),
                ),
            ).name
            for chunk in chunks[:5]:
                citation_pool.append(
                    create_chunk_citation(chunk, party_name)
                )

        resolved = ResolvedKnowledge(
            leaf_id=leaf_id,
            party_positions=party_positions,
            citation_pool=citation_pool,
            party_chunks=party_chunks,
        )

        logger.info(
            f"RAG-augmented follow-up for leaf {leaf_id}: "
            f"{sum(len(c) for c in party_chunks.values())} additional chunks"
        )

        # Now handle the conversation with the augmented knowledge
        return await self._handle_followup_with_resolved(
            session_id=session_id,
            exploration_id=exploration_id,
            exploration=exploration,
            leaf_id=leaf_id,
            user_message=user_message,
            message_type=MessageIntent.FOLLOWUP_QUESTION,
            context_name=context_name,
            parties_info=parties_info,
            conversation=conversation,
            resolved=resolved,
        )

    async def _handle_conversation_message(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        leaf_id: str,
        user_message: str,
        message_type: MessageIntent,
        context_name: str,
        parties_info: dict[str, PartyInfo],
        conversation: Conversation | None = None,
    ) -> dict:
        """Handle a conversation message — entry point that resolves knowledge.

        Always augments with RAG so follow-ups are not limited to pre-extracted
        positions. Delegates to _handle_followup_with_rag, which in turn calls
        _handle_followup_with_resolved once the RAG knowledge is ready.
        """
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)
        logger.info(
            f"Auto-augmenting follow-up with RAG for leaf {leaf_id}"
        )
        return await self._handle_followup_with_rag(
            session_id=session_id,
            exploration_id=exploration_id,
            exploration=exploration,
            leaf_id=leaf_id,
            user_message=user_message,
            context_name=context_name,
            parties_info=parties_info,
            conversation=conversation,
            positions_by_party=positions_by_party,
        )

    async def _handle_followup_with_resolved(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        leaf_id: str,
        user_message: str,
        message_type: MessageIntent,
        context_name: str,
        parties_info: dict[str, PartyInfo],
        conversation: Conversation | None,
        resolved: ResolvedKnowledge,
    ) -> dict:
        """Continuation called by _handle_followup_with_rag once knowledge is resolved.

        Receives the RAG-augmented ResolvedKnowledge and drives the LLM
        conversation turn. This is the only entry point that carries a
        resolved knowledge object — the public entry point is always
        _handle_conversation_message.
        """
        citation_pool = resolved.citation_pool
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)

        logger.info(
            f"Follow-up context for leaf {leaf_id}: "
            f"{len(resolved.party_positions)} parties, "
            f"{sum(len(p.positions) for p in resolved.party_positions.values())} positions, "
            f"{len(resolved.citation_pool)} citations"
            + (f", {sum(len(c) for c in resolved.party_chunks.values())} RAG chunks"
               if resolved.party_chunks else "")
        )

        # Get current navigation state
        navigation = self._navigation_states.get(session_id)
        if not navigation:
            navigation = NavigationState(
                exploration_id=exploration_id,
                current_path=[],
                breadcrumb=[],
            )

        # Use provided conversation or fetch if not provided
        if conversation is None:
            conversation = await self._repo.get_conversation(
                session_id, exploration_id, leaf_id
            )
        conversation_history = conversation.messages if conversation else []

        # Save user message
        now = datetime.now(timezone.utc)
        user_msg = Message(
            id=str(uuid4()),
            role=MessageRole.USER,
            type=MessageType.FOLLOWUP,
            content=user_message,
            timestamp=now,
        )
        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, user_msg
        )

        # Send user message event
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=user_msg,
                navigation=navigation,
            ),
        )

        # Send thinking event
        await self._send_thinking(session_id, "generating", "Formuliere Antwort...")

        # Get leaf node info for context
        leaf_node = exploration.tree.find_node(leaf_id)
        leaf_name = leaf_node.name if leaf_node else leaf_id
        leaf_description = leaf_node.description if leaf_node else ""

        # Build input for streaming
        handler_input = ConversationHandlerInput(
            message=user_message,
            leaf_id=leaf_id,
            leaf_name=leaf_name,
            leaf_description=leaf_description,
            conversation_history=conversation_history,
            resolved_knowledge=resolved,
            context_id=exploration.tree.exploration_id,
            context_name=context_name,
            parties_info=parties_info,
        )

        # Stream response directly from LLM
        stream_id = str(uuid4())
        message_id = str(uuid4())

        full_text = await self._stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._conversation_handler.stream_from_llm(handler_input),
            target_type="followup",
            target_id=leaf_id,
        )

        # Extract used citations — positions already have citation IDs in the text
        used_citations = extract_used_citations(full_text, citation_pool)

        # Record cited position ids for the study's Information Exposure metric.
        await self._log_study_exposure(session_id, used_citations)

        # Create and save the response message (with citations for persistence)
        response_message = Message(
            id=message_id,
            role=MessageRole.ASSISTANT,
            type=MessageType.FOLLOWUP,
            content=full_text,
            citations=used_citations,
            timestamp=datetime.now(timezone.utc),
        )

        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, response_message
        )

        # Generate claim-anchored follow-up questions, deduped against the
        # conversation history so we don't echo questions whose answer was
        # just given. The prompt has explicit fail-soft instructions to
        # return [] when no good follow-up exists.
        history_lines = self._format_leaf_conversation_history(conversation, limit=8)
        conversation_history_text = "\n".join(history_lines)

        available_context_parts: list[str] = []
        for party_id, party_data in resolved.party_positions.items():
            party_info = parties_info.get(party_id)
            party_name = party_info.name if party_info else party_id
            available_context_parts.append(f"\n## {party_name}")
            for pos in party_data.positions:
                available_context_parts.append(f"- {pos.position}")
        available_context = "\n".join(available_context_parts)

        suggested_questions = (
            await self._summary_generator.generate_suggested_questions(
                query=user_message,
                response=full_text,
                available_context=available_context,
                conversation_history=conversation_history_text,
            )
        )

        # Send conversation message event with citations
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=response_message,
                navigation=navigation,
                citations=used_citations,
                suggested_questions=suggested_questions,
            ),
        )

        return {
            "status": "accepted",
            "message_id": response_message.id,
        }

    # =========================================================================
    # Quick Summary & Factual Query Handling
    # =========================================================================

    async def _generate_quick_summary(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        detected_parties: list[str],
        context_id: str,
        session=None,
    ) -> dict:
        """Generate a quick summary with real-time LLM streaming.

        If ``session`` is provided, the recent conversation history is
        threaded into the prompt so the response can build on prior turns
        and resolve back-references naturally.
        """
        # 1. Send thinking event
        await self._send_thinking(session_id, "retrieving", "Sammle Informationen...")

        # 2. Retrieve chunks using RAG service
        chunks = await self._retrieve_chunks_for_summary(
            rag_query, context_id, detected_parties
        )

        # 3. Get context info and party details
        context_name, parties_info = await self._get_context_info(context_id)
        # For study contexts, ``parties_info`` already contains PartyInfo
        # objects whose .name / .long_name attributes are used downstream by
        # the summary formatters. For real contexts, load ContextParty objects
        # from Firebase so .logo_url and other optional fields remain available.
        if is_study_context(context_id):
            party_map = parties_info
        else:
            parties = await aget_parties_for_context(context_id)
            party_map = {p.party_id: p for p in parties}

        # 4. Format RAG context with document IDs and create citations
        rag_context, citations = self._format_rag_context_for_summary(chunks, party_map)

        # 5. Format parties list
        parties_list = self._format_parties_list_for_summary(
            detected_parties, party_map
        )

        # 5b. Format conversation history if a session was provided
        conversation_history_text = ""
        if session is not None:
            history_lines = self._format_conversation_history(session.messages)
            if history_lines:
                conversation_history_text = "\n".join(history_lines)

        # 6. Start streaming from LLM
        await self._send_thinking(
            session_id, "generating", "Erstelle Antwort..."
        )

        stream_id = str(uuid4())
        # In baseline study sessions, switch the prompt to a regular-
        # wahl.chat-style answer (no aspect-list Rückfrage on broad
        # questions, claim-only citations) so the baseline doesn't bleed
        # exploration-style behaviour into the contrast condition.
        is_baseline = session is not None and session.mode == SessionMode.BASELINE
        logger.info(
            "Quick summary path: session_id=%s mode=%s is_baseline=%s",
            session_id,
            session.mode.value if session else None,
            is_baseline,
        )
        summary_input = QuickSummaryInput(
            query=query,
            rag_context=rag_context,
            parties_list=parties_list,
            context_name=context_name,
            conversation_history=conversation_history_text,
            is_baseline=is_baseline,
        )

        # 7. Stream directly from LLM to SSE
        full_text = await self._stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._summary_generator.stream_quick_summary(summary_input),
            target_type="quick_summary",
            target_id="summary",
        )

        # 8. Extract only citations that were actually used by the LLM
        used_citations = extract_used_citations(full_text, citations)
        logger.info(
            f"Quick summary citations: {len(used_citations)} used "
            f"of {len(citations)} available"
        )

        # Record cited position ids for the study's Information Exposure metric.
        await self._log_study_exposure(session_id, used_citations)

        # 9. Generate suggested follow-up questions
        suggested_questions = (
            await self._summary_generator.generate_suggested_questions(
                query=query,
                response=full_text,
            )
        )

        # 10. Send QuickSummaryEvent with used citations and suggested questions
        await self._sse.send_to_session(
            session_id,
            QuickSummaryEvent(
                query_id=str(uuid4()),
                original_query=query,
                text=full_text,
                citations=used_citations,
                can_explore_deeper=True,
                suggested_questions=suggested_questions,
            ),
        )

        # 11. Send chat message event with citations and suggested questions
        await self._send_chat_message(
            session_id,
            full_text,
            citations=used_citations,
            can_explore_deeper=True,
            suggested_questions=suggested_questions,
        )

        # 12. Save assistant message with used citations
        assistant_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.ASSISTANT,
            content=full_text,
            citations=used_citations,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)

        return {"status": "summary_generated"}

    async def _retrieve_chunks_for_summary(
        self,
        rag_query: str,
        context_id: str,
        parties: list[str],
    ) -> list[RetrievedChunk]:
        """Retrieve chunks for quick summary generation."""
        all_chunks: list[RetrievedChunk] = []
        for party_id in parties:
            chunks = await self._rag_service.retrieve_chunks_for_party(
                query=rag_query,
                context_id=context_id,
                party_id=party_id,
                n_docs=3,  # Fewer docs per party for summary
                score_threshold=0.5,
            )
            all_chunks.extend(chunks)
        return all_chunks

    def _format_rag_context_for_summary(
        self,
        chunks: list[RetrievedChunk],
        party_map: dict,
    ) -> tuple[str, list[Citation]]:
        """Format RAG chunks with chunk IDs for citation.

        Returns:
            Tuple of (formatted context string, list of Citation objects)
        """
        if not chunks:
            return (
                "Keine relevanten Informationen in der Dokumentensammlung gefunden.",
                [],
            )

        citations: list[Citation] = []

        # Group chunks by party and create citations
        chunks_by_party: dict[str, list[RetrievedChunk]] = {}
        for chunk in chunks:
            if chunk.party_id not in chunks_by_party:
                chunks_by_party[chunk.party_id] = []
            chunks_by_party[chunk.party_id].append(chunk)

            party = party_map.get(chunk.party_id)
            party_display = party.name if party else chunk.party_id
            citations.append(
                create_chunk_citation(chunk, party_display)
            )

        # Format context grouped by party, using the canonical
        # "[chunk_id] content" bracket format shown to the LLM. Matches
        # conversation_handler._build_source_text so extraction via
        # extract_used_citations works identically in both paths.
        context_parts = []
        for party_id, party_chunks in chunks_by_party.items():
            party = party_map.get(party_id)
            party_name = party.name if party else party_id
            context_parts.append(f"\n## {party_name}\n")

            for chunk in party_chunks:
                context_parts.append(
                    f"[{chunk.chunk_id}] {chunk.content}\n\n"
                )

        return "".join(context_parts), citations

    def _format_parties_list_for_summary(
        self,
        party_ids: list[str],
        party_map: dict,
    ) -> str:
        """Format parties list for the prompt with party IDs for markers."""
        if not party_ids:
            return "Keine spezifischen Parteien"

        parts = []
        for party_id in party_ids:
            party = party_map.get(party_id)
            if party:
                # Include party_id explicitly for [PARTY:id] markers
                parts.append(f"- {party_id}: {party.name} ({party.long_name})")
            else:
                parts.append(f"- {party_id}: {party_id.upper()}")

        return "\n".join(parts)

    # Citation utilities moved to services/citation_utils.py

    async def _answer_factual_query(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        detected_parties: list[str],
        context_id: str,
    ) -> dict:
        """Answer a factual query directly without exploration."""
        # 1. Send thinking event
        await self._send_thinking(
            session_id, "retrieving", "Suche relevante Informationen..."
        )

        # 2. Get parties to query
        if not detected_parties:
            detected_parties = await self._get_default_parties(context_id)

        # 3. Retrieve chunks
        chunks = await self._retrieve_chunks_for_summary(
            rag_query, context_id, detected_parties
        )

        # If no chunks found, offer topic suggestions instead of an empty answer
        if not chunks:
            fallback_msg = (
                "Zu dieser Frage habe ich leider keine passenden Informationen "
                "in den Wahlprogrammen gefunden. Versuche es mit einem "
                "konkreteren Thema — zum Beispiel Mieten, Rente, Klima oder Wirtschaft."
            )
            await self._stream_text(
                session_id, fallback_msg, str(uuid4()), "system_message", "system",
            )
            await self._send_chat_message(session_id, fallback_msg)
            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=fallback_msg,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)
            return {"status": "no_results"}

        # 4. Get context info
        context_name, parties_info = await self._get_context_info(context_id)

        # 5. Generate answer using ConversationHandler (reuse existing agent)
        await self._send_thinking(session_id, "generating", "Formuliere Antwort...")

        # Build resolved knowledge from chunks for the handler
        resolved = self._build_resolved_from_chunks(chunks, detected_parties)

        # Build conversation history from session messages for follow-up context
        session = await self._repo.get_session(session_id)
        factual_history = []
        if session:
            from src.guided_exploration.models.conversation import (
                Message as ConvMessage,
                MessageRole,
                MessageType as ConvMessageType,
            )
            for msg in session.messages[-6:]:  # Last 6 messages for context
                if msg.type == SessionMessageType.USER and msg.content:
                    factual_history.append(ConvMessage(
                        id=msg.id,
                        role=MessageRole.USER,
                        type=ConvMessageType.FOLLOWUP,
                        content=msg.content,
                        timestamp=msg.timestamp,
                    ))
                elif msg.type == SessionMessageType.ASSISTANT and msg.content:
                    factual_history.append(ConvMessage(
                        id=msg.id,
                        role=MessageRole.ASSISTANT,
                        type=ConvMessageType.FOLLOWUP,
                        content=msg.content,
                        timestamp=msg.timestamp,
                    ))

        handler_input = ConversationHandlerInput(
            message=query,
            leaf_id="factual_query",
            conversation_history=factual_history,
            resolved_knowledge=resolved,
            context_id=context_id,
            context_name=context_name,
            parties_info=parties_info,
        )

        # 6. Build citation objects matching the chunk.chunk_id values that
        # the streaming LLM is shown in _build_source_text. For study
        # sessions these ids are the master position ids, so the extracted
        # citations can be logged directly against the master position list.
        rag_citations: list[Citation] = []
        for party_id, party_chunks in (resolved.party_chunks or {}).items():
            party_name = parties_info.get(
                party_id,
                PartyInfo(
                    party_id=party_id, name=party_id.upper(),
                    long_name=party_id.upper(),
                ),
            ).name
            for chunk in party_chunks[:5]:
                rag_citations.append(
                    create_chunk_citation(chunk, party_name)
                )

        # 7. Stream response directly from LLM with party markers
        stream_id = str(uuid4())
        full_text = await self._stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._conversation_handler.stream_from_llm(handler_input),
            target_type="quick_summary",
            target_id="factual",
        )

        # 8. Extract used citations — IDs in text match rag_citations IDs
        used_citations = extract_used_citations(full_text, rag_citations)

        # Record cited position ids for the study's Information Exposure metric.
        await self._log_study_exposure(session_id, used_citations)

        # 10. Generate suggested follow-up questions
        suggested_questions = (
            await self._summary_generator.generate_suggested_questions(
                query=query,
                response=full_text,
            )
        )

        # 11. Send chat message event with citations and suggested questions
        await self._send_chat_message(
            session_id,
            full_text,
            citations=used_citations,
            suggested_questions=suggested_questions,
        )

        # 12. Save messages with citations
        await self._repo.add_session_message(
            session_id,
            SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=full_text,
                citations=used_citations,
                timestamp=datetime.now(timezone.utc),
            ),
        )

        return {"status": "factual_answered"}

    def _build_resolved_from_chunks(
        self,
        chunks: list[RetrievedChunk],
        parties: list[str],
    ) -> ResolvedKnowledge:
        """Build ResolvedKnowledge from raw chunks for factual queries."""
        # Group chunks by party
        party_chunks: dict[str, list[RetrievedChunk]] = {}
        citation_pool: list[Citation] = []

        for chunk in chunks:
            if chunk.party_id not in party_chunks:
                party_chunks[chunk.party_id] = []
            party_chunks[chunk.party_id].append(chunk)

            # Build citation for each chunk (matching legacy system)
            doc_name = chunk.metadata.get("document_name", chunk.source_document)
            page_raw = chunk.source_page
            page_number = (int(page_raw) + 1) if page_raw is not None else None

            citation_pool.append(
                Citation(
                    id=chunk.chunk_id,
                    party=chunk.party_id,
                    document=doc_name,
                    section=chunk.source_section,
                    page=page_number,
                    document_publish_date=chunk.metadata.get("document_publish_date"),
                    url=chunk.metadata.get("url"),
                    source_document=chunk.metadata.get("source_document"),
                )
            )

        # Build party positions from chunks using ExtractedPosition
        party_positions: dict[str, ExtractedPosition] = {}
        for party_id in parties:
            if party_id in party_chunks:
                chunks_for_party = party_chunks[party_id][:3]

                # Create positions from chunks
                position_items = [
                    ExtractedPositionItem(
                        position=c.content[:150] + "..."
                        if len(c.content) > 150
                        else c.content,
                        quote=c.content[:300],
                        source_doc=c.source_document,
                        source_page=c.source_page,
                        position_type="position",
                        citation_id=c.chunk_id,
                    )
                    for c in chunks_for_party
                ]

                # Build summary from first chunk
                summary = chunks_for_party[0].content[:200] if chunks_for_party else ""

                party_positions[party_id] = ExtractedPosition(
                    party_id=party_id,
                    summary=summary,
                    positions=position_items,
                )

        return ResolvedKnowledge(
            leaf_id="factual",
            party_positions=party_positions,
            citation_pool=citation_pool,
            party_chunks=party_chunks,
        )

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _pregen_study_leaves(
        self,
        session_id: str,
        exploration_id: str,
        tree: ExplorationTree,
        context_name: str,
        parties_info: dict[str, PartyInfo],
    ) -> None:
        """
        Eagerly generate and persist initial content for every leaf in a
        study exploration. Runs fire-and-forget after the tree is built so
        participants never wait for LLM calls when they open a leaf.

        Each leaf is a registered ``asyncio.Task`` in
        ``self._pregen_leaf_tasks``. If a user navigates to a leaf mid-flight,
        ``_navigate_to_leaf`` awaits the existing task instead of firing a
        duplicate LLM call.

        Leaves that fail or time out stay at status='pending' and fall
        through to the normal lazy path on next open.
        """
        leaves = tree.root.get_leaf_nodes()
        if not leaves:
            return

        logger.info(
            f"Study pre-gen starting: {len(leaves)} leaves "
            f"(exploration={exploration_id})"
        )

        async def gen_and_persist(leaf: ExplorationNode) -> str | None:
            """Generate content + persist conversation for a leaf.

            Returns the leaf id on a fresh save, or None if the user beat us
            to it (conversation already exists) — in which case we skip to
            avoid clobbering live user state with an overwrite.
            """
            # Skip if a conversation already exists (user got there first
            # before this task got scheduled).
            existing = await self._repo.get_conversation(
                session_id, exploration_id, leaf.id
            )
            if existing and existing.messages:
                return None

            positions_by_party = tree.get_positions_by_party(leaf.id)
            leaf_citations = collect_leaf_citations(positions_by_party)
            path_nodes = tree.root.get_path_to(leaf.id) or []
            path = [n.id for n in path_nodes[1:]]
            content = await asyncio.wait_for(
                self._content_generator.execute(
                    ContentGeneratorInput(
                        subtopic_id=leaf.id,
                        subtopic_name=leaf.name,
                        path=path,
                        leaf_positions=positions_by_party,
                        leaf_citations=leaf_citations,
                        context_id=tree.exploration_id,
                        context_name=context_name,
                        parties_info=parties_info,
                        parties=leaf.party_ids,
                    )
                ),
                timeout=LEAF_PREGEN_TIMEOUT_SECONDS,
            )

            # No post-LLM re-check needed: _navigate_to_leaf awaits this
            # same task via the _pregen_leaf_tasks registry, and each leaf
            # has exactly one registered task — so no other writer races us.
            now = datetime.now(timezone.utc)
            initial_message = Message(
                id=str(uuid4()),
                role=MessageRole.ASSISTANT,
                type=MessageType.INITIAL_CONTENT,
                content=content,
                timestamp=now,
            )
            conversation = Conversation(
                leaf_id=leaf.id,
                messages=[initial_message],
                has_summary=False,
            )
            await self._repo.save_conversation(
                session_id, exploration_id, conversation
            )
            return leaf.id

        # Register one task per leaf so the navigator can coalesce.
        tasks: list[asyncio.Task] = []
        for leaf in leaves:
            key = (exploration_id, leaf.id)
            task = asyncio.create_task(gen_and_persist(leaf))
            self._pregen_leaf_tasks[key] = task
            tasks.append(task)

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            for leaf in leaves:
                self._pregen_leaf_tasks.pop((exploration_id, leaf.id), None)

        loaded_leaf_ids: list[str] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.warning(
                    f"Study pre-gen leaf failed: "
                    f"{type(result).__name__}: {result}"
                )
                continue
            if result is not None:
                loaded_leaf_ids.append(result)

        if loaded_leaf_ids:
            # Merge pending→loaded transitions onto the latest persisted
            # tree so we don't stomp on status changes the user made in
            # parallel (e.g. pending→started via _navigate_to_leaf).
            try:
                fresh = await self._repo.get_exploration(
                    session_id, exploration_id
                )
                if fresh is not None:
                    updated = False
                    for leaf_id in loaded_leaf_ids:
                        node = fresh.tree.find_node(leaf_id)
                        if node is not None and node.status == NodeStatus.PENDING:
                            node.status = NodeStatus.LOADED
                            updated = True
                    if updated:
                        await self._repo.update_tree(
                            session_id, exploration_id, fresh.tree
                        )
            except Exception as e:
                logger.warning(f"Study pre-gen tree persist failed: {e}")

        logger.info(
            f"Study pre-gen completed: {len(loaded_leaf_ids)}/{len(leaves)} "
            f"leaves loaded (exploration={exploration_id})"
        )

    async def _mark_leaf_explored(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
        tree: ExplorationTree,
    ) -> None:
        """Mark a leaf node as explored in the tree."""
        node = tree.find_node(leaf_id)
        if node is not None:
            node.status = NodeStatus.EXPLORED

        await self._repo.update_tree(session_id, exploration_id, tree)

    # =========================================================================
    # Conversation History Helpers
    # =========================================================================

    def _format_conversation_history(
        self,
        messages: list[SessionMessage],
        limit: int = 10,
    ) -> list[str]:
        """Format session messages as conversation history strings.

        Args:
            messages: List of session messages
            limit: Maximum number of recent messages to include

        Returns:
            List of formatted message strings for classifier context
        """
        history = []
        # Get last N messages that have content
        recent = [
            m
            for m in messages
            if m.content
            and m.type in (SessionMessageType.USER, SessionMessageType.ASSISTANT)
        ][-limit:]

        for msg in recent:
            role = "Nutzer" if msg.type == SessionMessageType.USER else "Assistent"
            # Truncate long messages
            msg_content = msg.content or ""
            content = (
                msg_content[:200] + "..." if len(msg_content) > 200 else msg_content
            )
            history.append(f"{role}: {content}")

        return history

    def _format_leaf_conversation_history(
        self,
        conversation: Conversation | None,
        limit: int = 10,
    ) -> list[str]:
        """Format leaf conversation messages as history strings.

        Args:
            conversation: The leaf conversation
            limit: Maximum number of recent messages to include

        Returns:
            List of formatted message strings for classifier context
        """
        if not conversation or not conversation.messages:
            return []

        history = []
        recent = conversation.messages[-limit:]

        for msg in recent:
            role = "Nutzer" if msg.role == MessageRole.USER else "Assistent"
            content = (
                msg.content
                if isinstance(msg.content, str)
                else "[Strukturierter Inhalt]"
            )
            # Truncate long messages (enough to preserve most back-references
            # while keeping the classifier prompt bounded).
            content = content[:800] + "..." if len(content) > 800 else content
            history.append(f"{role}: {content}")

        return history

    def _extract_last_assistant_message(
        self,
        conversation: Conversation | None,
    ) -> str | None:
        """Return the most recent assistant text message in full.

        The classifier needs the untruncated last assistant turn to resolve
        short affirmations ("gerne", "ja") against the specific question the
        assistant just asked. The truncated entry in the history list would
        hide the question if the message is longer than 200 chars.
        """
        if not conversation or not conversation.messages:
            return None
        for msg in reversed(conversation.messages):
            if msg.role != MessageRole.ASSISTANT:
                continue
            if isinstance(msg.content, str):
                return msg.content
        return None

    # =========================================================================
    # SSE Helpers
    # =========================================================================

    async def _send_thinking(
        self,
        session_id: str,
        stage: Literal["classifying", "planning", "retrieving", "generating"],
        message: str,
    ) -> None:
        """Send a thinking event."""
        await self._sse.send_to_session(
            session_id,
            ThinkingEvent(stage=stage, message=message),
        )

    async def _send_chat_message(
        self,
        session_id: str,
        message: str,
        citations: list[Citation] | None = None,
        can_explore_deeper: bool = False,
        query_id: str | None = None,
        suggested_questions: list[str] | None = None,
    ) -> None:
        """Send a chat message event."""
        await self._sse.send_to_session(
            session_id,
            ChatMessageEvent(
                type="chat_message",
                message_id=str(uuid4()),
                content=message,
                citations=citations or [],
                can_explore_deeper=can_explore_deeper,
                query_id=query_id,
                suggested_questions=suggested_questions or [],
            ),
        )

    async def _stream_text(
        self,
        session_id: str,
        content: str,
        stream_id: str,
        target_type: Literal[
            "initial_content", "followup", "analysis", "quick_summary", "system_message"
        ],
        target_id: str,
        section: str | None = None,
    ) -> None:
        """Stream content in word chunks."""
        words = content.split()
        chunk_index = 0

        for i in range(0, len(words), WORDS_PER_CHUNK):
            chunk = " ".join(words[i : i + WORDS_PER_CHUNK])
            if i + WORDS_PER_CHUNK < len(words):
                chunk += " "

            await self._sse.send_to_session(
                session_id,
                StreamChunkEvent(
                    stream_id=stream_id,
                    target_type=target_type,
                    target_id=target_id,
                    section=section,
                    chunk=chunk,
                    chunk_index=chunk_index,
                ),
            )
            chunk_index += 1
            await asyncio.sleep(CHUNK_DELAY)

        # Send stream end
        await self._sse.send_to_session(
            session_id,
            StreamEndEvent(
                stream_id=stream_id,
                target_type=target_type,
                target_id=target_id,
                complete=True,
            ),
        )

    async def _stream_from_llm(
        self,
        session_id: str,
        stream_id: str,
        llm_stream: "AsyncIterator[str]",
        target_type: Literal[
            "initial_content", "followup", "analysis", "quick_summary", "system_message"
        ],
        target_id: str,
        section: str | None = None,
    ) -> str:
        """
        Stream directly from LLM to SSE, returning the full text.

        This provides real-time streaming from the LLM to the frontend,
        rather than generating the full response first.

        Args:
            session_id: The session to stream to
            stream_id: Unique ID for this stream
            llm_stream: AsyncIterator yielding text chunks from LLM
            target_type: Type of content being streamed
            target_id: ID of the target (e.g., leaf_id)
            section: Optional section marker

        Returns:
            The complete accumulated text
        """
        full_text = ""
        chunk_index = 0

        async for chunk in llm_stream:
            full_text += chunk

            await self._sse.send_to_session(
                session_id,
                StreamChunkEvent(
                    stream_id=stream_id,
                    target_type=target_type,
                    target_id=target_id,
                    section=section,
                    chunk=chunk,
                    chunk_index=chunk_index,
                ),
            )
            chunk_index += 1

        # Send stream end
        await self._sse.send_to_session(
            session_id,
            StreamEndEvent(
                stream_id=stream_id,
                target_type=target_type,
                target_id=target_id,
                complete=True,
            ),
        )

        return full_text

    async def _send_error(
        self,
        session_id: str,
        code: str,
        message: str,
        recoverable: bool = True,
    ) -> None:
        """Send an error event to the session."""
        await self._sse.send_to_session(
            session_id,
            ErrorEvent(
                code=code,
                message=message,
                recoverable=recoverable,
                suggested_action=None,
            ),
        )

    # =========================================================================
    # Exploration Listing
    # =========================================================================

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
        """
        Request critical analysis for a leaf.

        Streams the analysis and then sends an AnalysisResultEvent.
        """
        # Get session for context
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Get exploration
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        # Get conversation for subtopic content
        conversation = await self._repo.get_conversation(
            session_id, exploration_id, leaf_id
        )
        if not conversation or not conversation.messages:
            await self._send_error(
                session_id,
                "no_content",
                "Kein Inhalt für Analyse verfügbar",
            )
            return {"status": "error", "code": "no_content"}

        # Get subtopic content from first message
        first_msg = conversation.messages[0]
        if not hasattr(first_msg.content, "summary"):
            await self._send_error(
                session_id,
                "invalid_content",
                "Ungültiger Inhalt für Analyse",
            )
            return {"status": "error", "code": "invalid_content"}

        subtopic_content = first_msg.content

        # Get positions for analysis context
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)
        if not positions_by_party:
            await self._send_error(
                session_id,
                "no_knowledge",
                "Kein Wissen für dieses Thema verfügbar",
            )
            return {"status": "error", "code": "no_knowledge"}

        # Get context info
        context_name, parties_info = await self._get_context_info(session.context_id)

        # Get leaf name
        leaf_name = self._get_leaf_name(exploration.tree, leaf_id)

        # Add a user message representing the analysis request
        now = datetime.now(timezone.utc)
        user_request_msg = Message(
            id=str(uuid4()),
            role=MessageRole.USER,
            type=MessageType.FOLLOWUP,
            content="Erstelle eine kritische Analyse zu diesem Thema.",
            timestamp=now,
        )
        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, user_request_msg
        )

        # Send user message event to frontend
        navigation = self._navigation_states.get(session_id)
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=user_request_msg,
                navigation=navigation,
            ),
        )

        # Build ResolvedKnowledge from positions for the analyzer
        analysis_positions: dict[str, ExtractedPosition] = {}
        analysis_citations: list[Citation] = []
        for party_id, positions in positions_by_party.items():
            analysis_positions[party_id] = ExtractedPosition(
                party_id=party_id,
                positions=[
                    ExtractedPositionItem(
                        position=c.content,
                        quote=c.quote,
                        source_doc=c.citation.document if c.citation else "",
                        source_page=c.citation.page if c.citation else None,
                        position_type=c.position_type,
                        citation_id=c.citation.id if c.citation else None,
                    )
                    for c in positions
                ],
            )
            for c in positions:
                if c.citation is not None:
                    analysis_citations.append(c.citation)

        resolved = ResolvedKnowledge(
            leaf_id=leaf_id,
            party_positions=analysis_positions,
            citation_pool=analysis_citations,
        )

        # Send thinking event
        await self._send_thinking(session_id, "generating", "Erstelle Analyse...")

        # Generate analysis (streaming)
        stream_id = str(uuid4())

        # Stream analysis using the analyzer agent
        analysis = await self._analyzer.execute(
            AnalyzerInput(
                leaf_id=leaf_id,
                leaf_name=leaf_name,
                subtopic_content=subtopic_content,
                resolved_knowledge=resolved,
                context_id=session.context_id,
                context_name=context_name,
                parties_info=parties_info,
            )
        )

        # Format analysis as markdown string
        feasibility_text = "\n".join(f"- {point}" for point in analysis.feasibility)
        considerations_text = "\n".join(
            f"- {point}" for point in analysis.considerations
        )

        analysis_markdown = f"""#### Kritische Analyse

{analysis.summary}

##### Hintergrund

{analysis.context}

##### Machbarkeit

{feasibility_text}

##### Zu bedenken

{considerations_text}"""

        # Stream the complete analysis as one message
        await self._stream_text(
            session_id,
            analysis_markdown,
            stream_id,
            "followup",
            leaf_id,
        )

        # Save as a regular assistant message with string content
        analysis_message = Message(
            id=str(uuid4()),
            role=MessageRole.ASSISTANT,
            type=MessageType.ANALYSIS,
            content=analysis_markdown,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_message_to_conversation(
            session_id, exploration_id, leaf_id, analysis_message
        )

        # Send conversation message event
        nav_state = self._navigation_states.get(session_id)
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=analysis_message,
                navigation=nav_state,
            ),
        )

        return {"status": "analysis_generated", "leaf_id": leaf_id}

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
        """
        End an exploration and optionally generate a final summary.

        Sends ExplorationCompleteEvent with closing summary.
        """
        # Get session for context
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        # Get exploration
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        # Idempotency guard — do not re-run summary LLM or re-send event (S1)
        from src.guided_exploration.models.exploration import ExplorationStatus as _ExplorationStatus
        if exploration.status == _ExplorationStatus.COMPLETED:
            return {"status": "already_completed"}

        # Build stats
        tree = exploration.tree
        all_leaves = tree.root.get_leaf_nodes()
        explored = [leaf.id for leaf in all_leaves if leaf.status == NodeStatus.EXPLORED]
        total_subtopics = len(all_leaves)

        stats = {
            "topics_explored": len(explored),
            "total_topics": total_subtopics,
            "completion_percentage": (
                int(len(explored) / total_subtopics * 100) if total_subtopics > 0 else 0
            ),
        }

        closing_summary = ""

        if generate_summary and explored:
            try:
                # Get context info
                context_name, _ = await self._get_context_info(session.context_id)

                # Get all leaf summaries
                all_summaries = await self._repo.get_all_summaries(
                    session_id, exploration_id
                )

                summary_tree = SummaryTree(summaries=all_summaries)

                # Generate final summary
                await self._send_thinking(
                    session_id, "generating", "Erstelle Zusammenfassung..."
                )

                final_summary = FinalSummary.model_validate(
                    await self._summary_generator.execute(
                        FinalSummaryInput(
                            exploration_id=exploration_id,
                            original_query=exploration.original_query,
                            summary_tree=summary_tree,
                            explored_subtopics=explored,
                            context_name=context_name,
                        )
                    )
                )

                closing_summary = final_summary.closing_summary

                # Stream the closing summary
                stream_id = str(uuid4())
                await self._stream_text(
                    session_id,
                    closing_summary,
                    stream_id,
                    "quick_summary",
                    exploration_id,
                )

                # Complete the exploration in repository
                await self._repo.complete_exploration(
                    session_id,
                    exploration_id,
                    final_summary.model_dump(mode="json"),
                )

            except Exception as e:
                logger.error(f"Failed to generate final summary: {e}")
                closing_summary = (
                    f"Vielen Dank für Ihre Erkundung zum Thema "
                    f"'{exploration.original_query}'. "
                    f"Sie haben {len(explored)} Themen erkundet."
                )
        else:
            closing_summary = (
                f"Erkundung zum Thema '{exploration.original_query}' beendet."
            )
            await self._repo.complete_exploration(
                session_id,
                exploration_id,
                {"closing_summary": closing_summary},
            )

        # Find unexplored leaves
        unexplored = [
            {"id": leaf.id, "name": leaf.name}
            for leaf in all_leaves
            if leaf.id not in explored
        ]

        # Send ExplorationCompleteEvent
        await self._sse.send_to_session(
            session_id,
            ExplorationCompleteEvent(
                exploration_id=exploration_id,
                closing_summary=closing_summary,
                stats=stats,
                next_actions={
                    "can_export": False,  # PDF export not yet implemented
                    "can_restart": True,
                    "suggested_topics": unexplored[:3] if unexplored else [],
                },
                unexplored_topics=unexplored,
            ),
        )

        # Clear navigation state
        if session_id in self._navigation_states:
            del self._navigation_states[session_id]

        return {
            "status": "exploration_ended",
            "exploration_id": exploration_id,
            "stats": stats,
        }


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

                # GPT-5.4 family (March 2026 flagship). gpt-5.4-mini for
                # classification, gpt-5.4 for content generation and
                # reasoning. Determinism for classification is enforced via
                # temperature=0.0 at the call site.
                registry = LLMRegistry()
                registry.register(LLMTier.FAST, LangChainLLMProvider(openai_gpt_5_4_mini))
                registry.register(LLMTier.BALANCED, LangChainLLMProvider(openai_gpt_5_4))
                registry.register(LLMTier.REASONING, LangChainLLMProvider(openai_gpt_5_4))
                registry.set_embeddings(LLMRegistry.create_openai_embeddings())

                _facade = GuidedExplorationFacade(sse_manager, repository, registry)
    return _facade
