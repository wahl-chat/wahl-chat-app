# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Explore-vs-summary choice flow + topic-direction selection."""

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from src.guided_exploration.agents import TopicScoutAgent, TopicScoutInput
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.handlers.exploration_lifecycle import (
    ExplorationLifecycleHandler,
)
from src.guided_exploration.handlers.quick_summary import QuickSummaryHandler
from src.guided_exploration.models import (
    ChoiceOption,
    ChoicePromptEvent,
    RetrievedChunk,
    SessionMessage,
    SessionMessageType,
    TopicDirectionItem,
    TopicDirectionsEvent,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.directions_cache import DirectionsCache
from src.guided_exploration.services.pending_query_store import (
    PendingQuery,
    PendingQueryStore,
)
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService

logger = logging.getLogger(__name__)


class ChoiceFlowHandler:
    """Drives the explore-vs-summary choice flow.

    Two entry points are exposed for the inbound router (the choice prompt
    and the direct topic-directions path) plus two public methods invoked
    by the API layer once the user picks (``handle_choice`` and
    ``handle_direction_choice``). The latter resolve the pending-query
    record, then hand off to either the quick-summary handler, the topic
    directions scout, or the exploration lifecycle.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        pending_queries: PendingQueryStore,
        directions_cache: DirectionsCache,
        topic_scout: TopicScoutAgent,
        quick_summary_handler: QuickSummaryHandler,
        exploration_lifecycle: ExplorationLifecycleHandler,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._pending_queries = pending_queries
        self._directions_cache = directions_cache
        self._topic_scout = topic_scout
        self._quick_summary_handler = quick_summary_handler
        self._exploration_lifecycle = exploration_lifecycle

    async def send_choice_prompt(
        self,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
    ) -> dict:
        """Send choice prompt and track pending query."""
        query_id = str(uuid4())

        self._pending_queries.register(
            PendingQuery(
                query_id=query_id,
                session_id=session_id,
                original_query=original_query,
                detected_parties=detected_parties,
                rag_query=rag_query,
            )
        )

        await self._streaming.send_thinking(
            session_id, "planning", "Identifiziere relevante Themen..."
        )

        options: tuple[ChoiceOption, ChoiceOption] = (
            ChoiceOption(
                id="summary",
                label="Schnelle Antwort",
                description="Kompakte Übersicht der Parteipositionen",
            ),
            ChoiceOption(
                id="explore",
                label="Thema vertiefen",
                description="Aspekte auswählen und Positionen im Detail vergleichen",
            ),
        )

        # Persist a research-only audit message so the study admin can see
        # the participant was offered the explore-vs-summary choice. The
        # chat frontend filters CHOICE_PROMPT messages out.
        choice_prompt_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.CHOICE_PROMPT,
            query_id=query_id,
            original_query=original_query,
            options=[opt.model_dump(mode="json") for opt in options],
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, choice_prompt_msg)

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

    async def send_topic_directions(
        self,
        session_id: str,
        original_query: str,
        detected_parties: list[str],
        rag_query: str,
        context_id: str,
    ) -> dict:
        """Scout topic directions and send them for user selection."""
        query_id = str(uuid4())

        if not detected_parties:
            detected_parties = await self._context_resolver.get_default_parties(
                context_id
            )

        scout_output = self._directions_cache.get(original_query, context_id)
        if scout_output is not None:
            logger.info(f"Cache hit for topic directions: '{original_query}'")
        else:
            await self._streaming.send_thinking(
                session_id, "retrieving", "Suche relevante Themenrichtungen..."
            )

            chunks = await self._rag_service.retrieve_chunks_for_parties(
                rag_query, context_id, detected_parties, n_docs=3
            )

            if not chunks:
                no_data_msg = (
                    "Zu diesem Thema habe ich leider keine passenden "
                    "Informationen in den Wahlprogrammen gefunden. "
                    "Versuche es mit einem konkreteren Thema oder einer "
                    "anderen Formulierung."
                )
                stream_id = str(uuid4())
                await self._streaming.stream_text(
                    session_id, no_data_msg, stream_id,
                    "quick_summary", "system",
                )
                await self._streaming.send_chat_message(session_id, no_data_msg)
                assistant_msg = SessionMessage(
                    id=str(uuid4()),
                    type=SessionMessageType.ASSISTANT,
                    content=no_data_msg,
                    timestamp=datetime.now(timezone.utc),
                )
                await self._repo.add_session_message(session_id, assistant_msg)
                return {"status": "no_data"}

            context_name, parties_info = (
                await self._context_resolver.get_context_info(context_id)
            )

            parties_map = {
                p_id: parties_info.get(p_id) for p_id in detected_parties
            }
            chunks_text = self._format_chunks_for_scout(chunks, parties_map)

            scout_output = await self._topic_scout.execute(
                TopicScoutInput(
                    query=original_query,
                    rag_chunks_text=chunks_text,
                    parties_info=parties_info,
                    context_name=context_name,
                )
            )

            if scout_output.cacheable:
                self._directions_cache.put(
                    original_query, context_id, scout_output
                )

        self._pending_queries.register(
            PendingQuery(
                query_id=query_id,
                session_id=session_id,
                original_query=original_query,
                detected_parties=detected_parties,
                rag_query=rag_query,
            )
        )

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
            await self._streaming.send_error(
                session_id,
                "query_not_found",
                "Anfrage nicht gefunden oder bereits bearbeitet",
            )
            return {"status": "error", "code": "query_not_found"}

        if pending.session_id != session_id:
            await self._streaming.send_error(
                session_id,
                "session_mismatch",
                "Anfrage gehört zu einer anderen Sitzung",
            )
            return {"status": "error", "code": "session_mismatch"}

        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        self._pending_queries.pop(query_id)

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

        if len(direction_names) >= 5:
            # All directions selected — no focus suffix
            focused_query = pending.original_query
        else:
            focus = ", ".join(direction_names)
            focused_query = f"{pending.original_query} — Fokus: {focus}"

        rag_focus = " ".join(direction_names)

        exploration_parties = (
            pending.detected_parties
            or await self._context_resolver.get_default_parties(session.context_id)
        )

        return await self._exploration_lifecycle.start_internal(
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
    ) -> dict:
        """Handle user's choice for explore vs summary."""
        pending = self._pending_queries.get(query_id)
        if not pending:
            await self._streaming.send_error(
                session_id,
                "query_not_found",
                "Anfrage nicht gefunden oder bereits bearbeitet",
            )
            return {"status": "error", "code": "query_not_found"}

        if pending.session_id != session_id:
            await self._streaming.send_error(
                session_id,
                "session_mismatch",
                "Anfrage gehört zu einer anderen Sitzung",
            )
            return {"status": "error", "code": "session_mismatch"}

        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        self._pending_queries.pop(query_id)

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

        if pending.detected_parties:
            exploration_parties = pending.detected_parties
        else:
            exploration_parties = await self._context_resolver.get_default_parties(
                session.context_id
            )

        if choice == "explore":
            return await self.send_topic_directions(
                session_id=session_id,
                original_query=pending.original_query,
                detected_parties=exploration_parties,
                rag_query=pending.rag_query,
                context_id=session.context_id,
            )
        else:
            return await self._quick_summary_handler.generate(
                session_id=session_id,
                query=pending.original_query,
                rag_query=pending.rag_query,
                detected_parties=exploration_parties,
                context_id=session.context_id,
                query_kind="broad",
                session=session,
            )
