# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Follow-up message handling within an active exploration leaf."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.guided_exploration.agents import (
    ConversationHandlerAgent,
    ConversationHandlerInput,
    MessageClassifierAgent,
    MessageClassifierInput,
    SummaryGeneratorAgent,
)
from src.guided_exploration.agents.followup_router import (
    FollowupRouterAgent,
    FollowupRouterInput,
    FollowupRoute,
    LeafInfo,
)
from src.guided_exploration.agents.followup_router.prompts import (
    format_positions_for_routing,
)
from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.handlers.navigation import NavigationHandler
from src.guided_exploration.models import (
    Citation,
    Conversation,
    ConversationMessageEvent,
    Exploration,
    ExtractedPosition,
    ExtractedPositionItem,
    Message,
    MessageRole,
    MessageType,
    NavigationState,
    ResolvedKnowledge,
)
from src.guided_exploration.models.classification import MessageIntent
from src.guided_exploration.models.events import TopicSwitchSuggestedEvent
from src.guided_exploration.services.citation_utils import (
    create_citation_from_chunk as create_chunk_citation,
    extract_used_citations,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.conversation_history import (
    extract_last_assistant_message,
    format_leaf_history,
)
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_exposure import StudyExposureLogger

logger = logging.getLogger(__name__)


class FollowupHandler:
    """Drives the follow-up conversation chain inside a leaf.

    Classifies the user message, optionally routes through the followup
    router (on-topic/needs-RAG/related/off-topic), and either delegates to
    the navigation handler (navigation commands) or runs a RAG-augmented
    LLM turn that streams back via the conversation handler agent.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        navigation_states: NavigationStateStore,
        navigation_handler: NavigationHandler,
        message_classifier: MessageClassifierAgent,
        followup_router: FollowupRouterAgent,
        conversation_handler: ConversationHandlerAgent,
        summary_generator: SummaryGeneratorAgent,
        study_exposure: StudyExposureLogger,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._navigation_states = navigation_states
        self._navigation_handler = navigation_handler
        self._message_classifier = message_classifier
        self._followup_router = followup_router
        self._conversation_handler = conversation_handler
        self._summary_generator = summary_generator
        self._study_exposure = study_exposure

    async def handle(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
        user_message: str,
    ) -> dict:
        """Handle a user message within an active exploration."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._streaming.send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        context_name, parties_info = await self._context_resolver.get_context_info(
            session.context_id
        )

        conversation = await self._repo.get_conversation(
            session_id, exploration_id, leaf_id
        )
        conversation_history = format_leaf_history(conversation)
        last_assistant_message = extract_last_assistant_message(conversation)

        await self._streaming.send_thinking(
            session_id, "classifying", "Analysiere Ihre Nachricht..."
        )

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

        if classification.intent == MessageIntent.NAVIGATION_COMMAND:
            return await self._navigation_handler.handle_navigation_command(
                session_id,
                exploration_id,
                exploration,
                leaf_id,
                classification.navigation_target,
            )

        logger.info(
            f"Message classified as {classification.intent.value} "
            f"(confidence: {classification.confidence:.2f})"
        )

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
        leaf_node = exploration.tree.find_node(leaf_id)
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)

        all_leaves = exploration.tree.root.get_leaf_nodes()
        other_leaves = [
            LeafInfo(id=node.id, name=node.name, description=node.description)
            for node in all_leaves
            if node.id != leaf_id
        ]

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

        # OFF_TOPIC — polite redirect
        await self._streaming.send_thinking(session_id, "generating", "")

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
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        await self._streaming.send_thinking(
            session_id, "retrieving", "Suche weitere Details..."
        )

        search_query = rag_query or user_message
        party_ids = list(positions_by_party.keys())

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

        party_positions: dict[str, ExtractedPosition] = {}
        citation_pool: list[Citation] = []
        party_chunks: dict[str, list] = {}

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

        for result in results:
            if isinstance(result, BaseException):
                continue
            party_id, chunks = result
            party_chunks[party_id] = chunks
            party_name = parties_info.get(
                party_id,
                PartyInfo(
                    party_id=party_id,
                    name=party_id.upper(),
                    long_name=party_id.upper(),
                ),
            ).name
            for chunk in chunks[:5]:
                citation_pool.append(create_chunk_citation(chunk, party_name))

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
        """Resolve knowledge (always RAG-augmented) and run the LLM turn."""
        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)
        logger.info(f"Auto-augmenting follow-up with RAG for leaf {leaf_id}")
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
        """Run the LLM turn with RAG-augmented knowledge and persist results."""
        citation_pool = resolved.citation_pool

        logger.info(
            f"Follow-up context for leaf {leaf_id}: "
            f"{len(resolved.party_positions)} parties, "
            f"{sum(len(p.positions) for p in resolved.party_positions.values())} positions, "
            f"{len(resolved.citation_pool)} citations"
            + (
                f", {sum(len(c) for c in resolved.party_chunks.values())} RAG chunks"
                if resolved.party_chunks
                else ""
            )
        )

        navigation = self._navigation_states.get(session_id)
        if not navigation:
            navigation = NavigationState(
                exploration_id=exploration_id,
                current_path=[],
                breadcrumb=[],
            )

        if conversation is None:
            conversation = await self._repo.get_conversation(
                session_id, exploration_id, leaf_id
            )
        conversation_history = conversation.messages if conversation else []

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
                navigation=navigation,
            ),
        )

        await self._streaming.send_thinking(
            session_id, "generating", "Formuliere Antwort..."
        )

        leaf_node = exploration.tree.find_node(leaf_id)
        leaf_name = leaf_node.name if leaf_node else leaf_id
        leaf_description = leaf_node.description if leaf_node else ""

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

        stream_id = str(uuid4())
        message_id = str(uuid4())

        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._conversation_handler.stream_from_llm(handler_input),
            target_type="followup",
            target_id=leaf_id,
        )

        used_citations = extract_used_citations(full_text, citation_pool)

        await self._study_exposure.log(session_id, used_citations)

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

        history_lines = format_leaf_history(conversation, limit=8)
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
