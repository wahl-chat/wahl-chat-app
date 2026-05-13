# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Guided main-chat reply handler.

Handles both broad-overview queries (post-choice-flow "summary") and
focused factual queries from the inbound router. Both call
``QuickSummaryAgent.stream``; the existing system prompt's "Schritt 0
— Fokus prüfen" branch handles broad-vs-focused at the prompt level.
``query_kind`` is preserved on the call signature so the intent stays
explicit and the retrieval depth differs.
"""

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from src.firebase_service import aget_parties_for_context
from src.guided_exploration.agents.main_chat_followup_generator import (
    MainChatFollowUpGenerator,
    MainChatFollowUpInput,
)
from src.guided_exploration.agents.quick_summary import (
    QuickSummaryAgent,
    QuickSummaryInput,
)
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    FlaggedCitation,
    QuickSummaryEvent,
    Session,
    SessionMessage,
    SessionMessageType,
)
from src.guided_exploration.services.citation_utils import (
    extract_fabricated_citation_ids,
    extract_used_citations,
)
from src.guided_exploration.services.rag_formatting import (
    format_parties_list,
    format_rag_context,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.conversation_history import (
    format_session_history,
)
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_context import is_study_context
from src.guided_exploration.services.study_exposure import StudyExposureLogger
from src.guided_exploration.services.study_positions import (
    format_topic_positions_for_chips,
)

logger = logging.getLogger(__name__)


class QuickSummaryHandler:
    """Owns guided main-chat replies (broad and focused)."""

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        quick_summary_agent: QuickSummaryAgent,
        main_chat_followup_generator: MainChatFollowUpGenerator,
        study_exposure: StudyExposureLogger,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._quick_summary_agent = quick_summary_agent
        self._main_chat_followup = main_chat_followup_generator
        self._study_exposure = study_exposure

    async def generate(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        detected_parties: list[str],
        context_id: str,
        session: Session,
        query_kind: Literal["broad", "focused"] = "broad",
    ) -> dict:
        """Generate a guided reply with real-time LLM streaming.

        ``query_kind`` controls retrieval depth and the empty-pool
        fallback: focused queries pull fewer chunks and surface a
        no-results message when the pool is empty; broad queries always
        stream a response.
        """
        await self._streaming.send_thinking(
            session_id, "retrieving", "Sammle Informationen..."
        )

        if not detected_parties:
            detected_parties = await self._context_resolver.get_default_parties(
                context_id
            )

        n_docs = 3 if query_kind == "focused" else 6
        chunks = await self._rag_service.retrieve_chunks_for_parties(
            rag_query, context_id, detected_parties, n_docs=n_docs
        )

        if query_kind == "focused" and not chunks:
            return await self._emit_no_results(session_id)

        context_name, parties_info = await self._context_resolver.get_context_info(
            context_id
        )
        if is_study_context(context_id):
            party_map = parties_info
        else:
            parties = await aget_parties_for_context(context_id)
            party_map = {p.party_id: p for p in parties}

        rag_context, citations = format_rag_context(chunks, party_map)
        parties_list = format_parties_list(detected_parties, party_map)

        conversation_history_text = ""
        history_lines = format_session_history(session.messages)
        if history_lines:
            conversation_history_text = "\n".join(history_lines)

        await self._streaming.send_thinking(
            session_id, "generating", "Erstelle Antwort..."
        )

        stream_id = str(uuid4())
        logger.info(
            "Quick summary path: session_id=%s query_kind=%s",
            session_id,
            query_kind,
        )
        summary_input = QuickSummaryInput(
            query=query,
            rag_context=rag_context,
            parties_list=parties_list,
            context_name=context_name,
            conversation_history=conversation_history_text,
        )

        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._quick_summary_agent.stream(summary_input),
            target_type="quick_summary",
            target_id="summary" if query_kind == "broad" else "factual",
        )

        used_citations = extract_used_citations(full_text, citations)
        logger.info(
            f"Quick summary citations: {len(used_citations)} used "
            f"of {len(citations)} available"
        )

        fabricated_ids = extract_fabricated_citation_ids(full_text, citations)
        if fabricated_ids:
            logger.warning(
                f"Quick summary fabricated citations session={session_id} "
                f"ids={fabricated_ids} pool_size={len(citations)}"
            )
            await self._repo.add_flagged_citation(
                session_id,
                FlaggedCitation(
                    handler="quick_summary",
                    fabricated_ids=fabricated_ids,
                    pool_size=len(citations),
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

        await self._study_exposure.log(session_id, used_citations)

        chip_history_text = ""
        if session is not None:
            chip_history_lines = format_session_history(
                session.messages, per_message_chars=1500
            )
            if chip_history_lines:
                chip_history_text = "\n".join(chip_history_lines)
        chips = await self._main_chat_followup.generate(
            MainChatFollowUpInput(
                query=query,
                response=full_text,
                available_context=rag_context,
                topic_positions=format_topic_positions_for_chips(context_id),
                conversation_history=chip_history_text,
            )
        )
        suggested_questions = chips.questions

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

        await self._streaming.send_chat_message(
            session_id,
            full_text,
            citations=used_citations,
            can_explore_deeper=True,
            suggested_questions=suggested_questions,
        )

        assistant_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.ASSISTANT,
            content=full_text,
            citations=used_citations,
            suggested_followups=list(suggested_questions),
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)

        return {
            "status": "factual_answered" if query_kind == "focused" else "summary_generated"
        }

    async def _emit_no_results(self, session_id: str) -> dict:
        fallback_msg = (
            "Zu dieser Frage habe ich leider keine passenden Informationen "
            "in den Wahlprogrammen gefunden. Versuche es mit einem "
            "konkreteren Thema — zum Beispiel Mieten, Rente, Klima oder Wirtschaft."
        )
        await self._streaming.stream_text(
            session_id,
            fallback_msg,
            str(uuid4()),
            "system_message",
            "system",
        )
        await self._streaming.send_chat_message(session_id, fallback_msg)
        assistant_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.ASSISTANT,
            content=fallback_msg,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)
        return {"status": "no_results"}

