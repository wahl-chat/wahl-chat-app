# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Top-of-funnel summary path — RAG retrieve, stream, persist as a session msg."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.firebase_service import aget_parties_for_context
from src.guided_exploration.agents import (
    QuickSummaryInput,
    SummaryGeneratorAgent,
)
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    Citation,
    FlaggedCitation,
    QuickSummaryEvent,
    RetrievedChunk,
    SessionMessage,
    SessionMessageType,
    SessionMode,
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

logger = logging.getLogger(__name__)


class QuickSummaryHandler:
    """Generates a single-shot summary in response to a broad query.

    Resolves party set + RAG context, streams the summary from the
    summary-generator agent, and emits both the rich ``QuickSummaryEvent``
    (for the explore-deeper UI) and a plain ``ChatMessageEvent`` for the
    transcript.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        rag_service: RAGService,
        context_resolver: ContextResolver,
        summary_generator: SummaryGeneratorAgent,
        study_exposure: StudyExposureLogger,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._rag_service = rag_service
        self._context_resolver = context_resolver
        self._summary_generator = summary_generator
        self._study_exposure = study_exposure

    async def generate(
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
        await self._streaming.send_thinking(
            session_id, "retrieving", "Sammle Informationen..."
        )

        chunks = await self._rag_service.retrieve_chunks_for_parties(
            rag_query, context_id, detected_parties, n_docs=5
        )

        context_name, parties_info = await self._context_resolver.get_context_info(
            context_id
        )
        # For study contexts, ``parties_info`` already contains PartyInfo
        # objects whose .name / .long_name attributes are used downstream by
        # the summary formatters. For real contexts, load ContextParty objects
        # from Firebase so .logo_url and other optional fields remain available.
        if is_study_context(context_id):
            party_map = parties_info
        else:
            parties = await aget_parties_for_context(context_id)
            party_map = {p.party_id: p for p in parties}

        rag_context, citations = self._format_rag_context(chunks, party_map)
        parties_list = self._format_parties_list(detected_parties, party_map)

        conversation_history_text = ""
        if session is not None:
            history_lines = format_session_history(session.messages)
            if history_lines:
                conversation_history_text = "\n".join(history_lines)

        await self._streaming.send_thinking(
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

        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=self._summary_generator.stream_quick_summary(summary_input),
            target_type="quick_summary",
            target_id="summary",
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

        suggested_questions = (
            await self._summary_generator.generate_suggested_questions(
                query=query,
                response=full_text,
                available_context=rag_context,
                conversation_history=conversation_history_text,
                is_baseline=is_baseline,
            )
        )

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
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)

        return {"status": "summary_generated"}

    def _format_rag_context(
        self,
        chunks: list[RetrievedChunk],
        party_map: dict,
    ) -> tuple[str, list[Citation]]:
        """Render chunks for the LLM and collect Citation objects in parallel.

        Output format mirrors ``conversation_handler._build_source_text``
        ("[chunk_id] content") so ``extract_used_citations`` can resolve
        markers identically across both paths.
        """
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
        """Render the parties block for the prompt with ids preserved for [PARTY:id]."""
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
