# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Baseline (production-wahl.chat-shaped) reply handler.

Owns the full baseline path end-to-end: RAG retrieval, baseline-prompt
streaming via ``BaselineAgent.stream``, baseline-style 3-fixed-slot
chips via ``MainChatFollowUpGenerator``, and persistence as a session
message. No guided affordances are surfaced — this handler exists so
the prompt path is unambiguous from the call site downward.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.firebase_service import aget_parties_for_context
from src.guided_exploration.agents.baseline import (
    BaselineAgent,
    BaselineInput,
)
from src.guided_exploration.agents.main_chat_followup_generator import (
    MainChatFollowUpGenerator,
    MainChatFollowUpInput,
)
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    Citation,
    FlaggedCitation,
    QuickSummaryEvent,
    RetrievedChunk,
    SessionMessage,
    SessionMessageType,
)
from src.guided_exploration.services.citation_utils import (
    create_citation_from_chunk as create_chunk_citation,
    extract_fabricated_citation_ids,
    extract_used_citations,
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


class BaselineHandler:
    """Owns the baseline reply path end-to-end."""

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        baseline_agent: BaselineAgent,
        main_chat_followup_generator: MainChatFollowUpGenerator,
        study_exposure: StudyExposureLogger,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._baseline_agent = baseline_agent
        self._main_chat_followup = main_chat_followup_generator
        self._study_exposure = study_exposure

    async def generate(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        detected_parties: list[str],
        context_id: str,
        session,
    ) -> dict:
        """Generate a baseline reply with real-time LLM streaming.

        ``session`` is required (not optional) — the baseline path needs
        the session's ``max_claims_per_party`` cap and conversation
        history to mirror the production wahl.chat assistant.
        """
        await self._streaming.send_thinking(
            session_id, "retrieving", "Sammle Informationen..."
        )

        chunks = await self._rag_service.retrieve_chunks_for_parties(
            rag_query, context_id, detected_parties, n_docs=10
        )

        context_name, parties_info = await self._context_resolver.get_context_info(
            context_id
        )
        if is_study_context(context_id):
            party_map = parties_info
        else:
            parties = await aget_parties_for_context(context_id)
            party_map = {p.party_id: p for p in parties}

        rag_context, citations = self._format_rag_context(chunks, party_map)
        parties_list = self._format_parties_list(detected_parties, party_map)

        history_lines = format_session_history(session.messages)
        conversation_history_text = "\n".join(history_lines) if history_lines else ""

        await self._streaming.send_thinking(
            session_id, "generating", "Erstelle Antwort..."
        )

        stream_id = str(uuid4())
        max_claims_per_party = session.max_claims_per_party
        logger.info(
            "Baseline path: session_id=%s mode=%s max_claims_per_party=%s",
            session_id,
            session.mode.value,
            max_claims_per_party,
        )
        baseline_input = BaselineInput(
            query=query,
            rag_context=rag_context,
            parties_list=parties_list,
            context_name=context_name,
            conversation_history=conversation_history_text,
            max_claims_per_party=max_claims_per_party,
        )

        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._baseline_agent.stream(baseline_input),
            target_type="quick_summary",
            target_id="summary",
        )

        used_citations = extract_used_citations(full_text, citations)
        logger.info(
            f"Baseline citations: {len(used_citations)} used "
            f"of {len(citations)} available"
        )

        fabricated_ids = extract_fabricated_citation_ids(full_text, citations)
        if fabricated_ids:
            logger.warning(
                f"Baseline fabricated citations session={session_id} "
                f"ids={fabricated_ids} pool_size={len(citations)}"
            )
            await self._repo.add_flagged_citation(
                session_id,
                FlaggedCitation(
                    handler="baseline",
                    fabricated_ids=fabricated_ids,
                    pool_size=len(citations),
                    occurred_at=datetime.now(timezone.utc),
                ),
            )

        await self._study_exposure.log(session_id, used_citations)

        chip_history_lines = format_session_history(
            session.messages, per_message_chars=1500
        )
        chip_history_text = "\n".join(chip_history_lines) if chip_history_lines else ""
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
                can_explore_deeper=False,
                suggested_questions=suggested_questions,
            ),
        )

        await self._streaming.send_chat_message(
            session_id,
            full_text,
            citations=used_citations,
            can_explore_deeper=False,
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

        return {"status": "summary_generated"}

    def _format_rag_context(
        self,
        chunks: list[RetrievedChunk],
        party_map: dict,
    ) -> tuple[str, list[Citation]]:
        if not chunks:
            return (
                "Keine relevanten Informationen in der Dokumentensammlung gefunden.",
                [],
            )

        citations: list[Citation] = []
        chunks_by_party: dict[str, list[RetrievedChunk]] = {}
        for chunk in chunks:
            if chunk.party_id not in chunks_by_party:
                chunks_by_party[chunk.party_id] = []
            chunks_by_party[chunk.party_id].append(chunk)

            party = party_map.get(chunk.party_id)
            party_display = party.name if party else chunk.party_id
            citations.append(create_chunk_citation(chunk, party_display))

        context_parts = []
        for party_id, party_chunks in chunks_by_party.items():
            party = party_map.get(party_id)
            party_name = party.name if party else party_id
            context_parts.append(f"\n## {party_name}\n")
            for chunk in party_chunks:
                context_parts.append(f"[{chunk.chunk_id}] {chunk.content}\n\n")

        return "".join(context_parts), citations

    def _format_parties_list(
        self,
        party_ids: list[str],
        party_map: dict,
    ) -> str:
        if not party_ids:
            return "Keine spezifischen Parteien"

        parts = []
        for party_id in party_ids:
            party = party_map.get(party_id)
            if party:
                parts.append(f"- {party_id}: {party.name} ({party.long_name})")
            else:
                parts.append(f"- {party_id}: {party_id.upper()}")

        return "\n".join(parts)
