# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Direct-answer path for factual queries — RAG → ConversationHandler stream."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.guided_exploration.agents import (
    ConversationHandlerAgent,
    ConversationHandlerInput,
    SummaryGeneratorAgent,
)
from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.models import (
    Citation,
    ExtractedPosition,
    ExtractedPositionItem,
    ResolvedKnowledge,
    RetrievedChunk,
    SessionMessage,
    SessionMessageType,
)
from src.guided_exploration.services.citation_utils import (
    create_citation_from_chunk as create_chunk_citation,
    extract_used_citations,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.conversation_history import (
    format_session_history,
)
from src.guided_exploration.services.rag_service import RAGService
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_exposure import StudyExposureLogger

logger = logging.getLogger(__name__)


class FactualQueryHandler:
    """Answers a focused factual query without spinning up an exploration.

    Reuses the conversation-handler agent so citation handling matches the
    in-leaf follow-up path; the only structural difference is that the
    'leaf' here is the synthetic ``factual_query`` placeholder.
    """

    def __init__(
        self,
        repo: SessionRepository,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        conversation_handler: ConversationHandlerAgent,
        summary_generator: SummaryGeneratorAgent,
        study_exposure: StudyExposureLogger,
        get_default_parties,
    ) -> None:
        self._repo = repo
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._conversation_handler = conversation_handler
        self._summary_generator = summary_generator
        self._study_exposure = study_exposure
        self._get_default_parties = get_default_parties

    async def answer(
        self,
        session_id: str,
        query: str,
        rag_query: str,
        detected_parties: list[str],
        context_id: str,
    ) -> dict:
        """Answer a factual query directly without exploration."""
        await self._streaming.send_thinking(
            session_id, "retrieving", "Suche relevante Informationen..."
        )

        if not detected_parties:
            detected_parties = await self._get_default_parties(context_id)

        chunks = await self._rag_service.retrieve_chunks_for_parties(
            rag_query, context_id, detected_parties, n_docs=3
        )

        # If no chunks found, offer topic suggestions instead of an empty answer
        if not chunks:
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

        context_name, parties_info = await self._context_resolver.get_context_info(
            context_id
        )

        await self._streaming.send_thinking(
            session_id, "generating", "Formuliere Antwort..."
        )

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
            for msg in session.messages[-6:]:
                if msg.type == SessionMessageType.USER and msg.content:
                    factual_history.append(
                        ConvMessage(
                            id=msg.id,
                            role=MessageRole.USER,
                            type=ConvMessageType.FOLLOWUP,
                            content=msg.content,
                            timestamp=msg.timestamp,
                        )
                    )
                elif msg.type == SessionMessageType.ASSISTANT and msg.content:
                    factual_history.append(
                        ConvMessage(
                            id=msg.id,
                            role=MessageRole.ASSISTANT,
                            type=ConvMessageType.FOLLOWUP,
                            content=msg.content,
                            timestamp=msg.timestamp,
                        )
                    )

        handler_input = ConversationHandlerInput(
            message=query,
            leaf_id="factual_query",
            conversation_history=factual_history,
            resolved_knowledge=resolved,
            context_id=context_id,
            context_name=context_name,
            parties_info=parties_info,
        )

        # Build citation objects matching the chunk.chunk_id values that
        # the streaming LLM is shown in _build_source_text. For study
        # sessions these ids are the master position ids, so the extracted
        # citations can be logged directly against the master position list.
        rag_citations: list[Citation] = []
        for party_id, party_chunks in (resolved.party_chunks or {}).items():
            party_name = parties_info.get(
                party_id,
                PartyInfo(
                    party_id=party_id,
                    name=party_id.upper(),
                    long_name=party_id.upper(),
                ),
            ).name
            for chunk in party_chunks[:5]:
                rag_citations.append(create_chunk_citation(chunk, party_name))

        stream_id = str(uuid4())
        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._conversation_handler.stream_from_llm(handler_input),
            target_type="quick_summary",
            target_id="factual",
        )

        used_citations = extract_used_citations(full_text, rag_citations)

        await self._study_exposure.log(session_id, used_citations)

        available_context_parts: list[str] = []
        for party_id, party_data in resolved.party_positions.items():
            party_info = parties_info.get(party_id)
            party_name = party_info.name if party_info else party_id
            available_context_parts.append(f"\n## {party_name}")
            for pos in party_data.positions:
                available_context_parts.append(f"- {pos.position}")
        available_context = "\n".join(available_context_parts)

        conversation_history_text = ""
        if session is not None:
            history_lines = format_session_history(session.messages)
            if history_lines:
                conversation_history_text = "\n".join(history_lines)

        suggested_questions = (
            await self._summary_generator.generate_suggested_questions(
                query=query,
                response=full_text,
                available_context=available_context,
                conversation_history=conversation_history_text,
            )
        )

        await self._streaming.send_chat_message(
            session_id,
            full_text,
            citations=used_citations,
            suggested_questions=suggested_questions,
        )

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
        party_chunks: dict[str, list[RetrievedChunk]] = {}
        citation_pool: list[Citation] = []

        for chunk in chunks:
            if chunk.party_id not in party_chunks:
                party_chunks[chunk.party_id] = []
            party_chunks[chunk.party_id].append(chunk)

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

        party_positions: dict[str, ExtractedPosition] = {}
        for party_id in parties:
            if party_id in party_chunks:
                chunks_for_party = party_chunks[party_id][:3]

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
