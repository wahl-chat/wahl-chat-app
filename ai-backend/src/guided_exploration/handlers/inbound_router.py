# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Top-of-funnel router: classifies inbound messages and dispatches them."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage

from src.guided_exploration.agents import (
    QueryClassifierAgent,
    QueryClassifierInput,
)
from src.guided_exploration.agents.llm_provider import LLMRegistry, LLMTier
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.handlers.choice_flow import ChoiceFlowHandler
from src.guided_exploration.handlers.factual_query import FactualQueryHandler
from src.guided_exploration.handlers.followup import FollowupHandler
from src.guided_exploration.handlers.quick_summary import QuickSummaryHandler
from src.guided_exploration.models import (
    QueryType,
    SessionMessage,
    SessionMessageType,
    SessionMode,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.conversation_history import (
    format_session_history,
)
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService

logger = logging.getLogger(__name__)


class InboundRouter:
    """Routes inbound user messages.

    Dispatch order: in-exploration → followup; baseline mode → baseline
    sub-router; otherwise classify and dispatch (exploratory → choice flow,
    meta → conversational meta answer, factual → factual handler,
    clarification/unknown → streamed system message). Both the guided and
    baseline branches persist the user message before answering so the
    conversation transcript is complete even on early returns.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        context_resolver: ContextResolver,
        query_classifier: QueryClassifierAgent,
        llm_registry: LLMRegistry,
        choice_flow: ChoiceFlowHandler,
        quick_summary_handler: QuickSummaryHandler,
        factual_query_handler: FactualQueryHandler,
        followup_handler: FollowupHandler,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._context_resolver = context_resolver
        self._query_classifier = query_classifier
        self._llm_registry = llm_registry
        self._choice_flow = choice_flow
        self._quick_summary_handler = quick_summary_handler
        self._factual_query_handler = factual_query_handler
        self._followup_handler = followup_handler

    async def handle_message(
        self,
        session_id: str,
        content: str,
        exploration_context: dict | None = None,
    ) -> dict:
        """Handle a user message at the session level."""
        session = await self._repo.get_session(session_id)
        if not session:
            await self._streaming.send_error(
                session_id,
                "session_not_found",
                "Sitzung nicht gefunden",
            )
            return {"status": "error", "code": "session_not_found"}

        await self._repo.update_session_activity(session_id)

        if exploration_context:
            return await self._followup_handler.handle(
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

        await self._streaming.send_thinking(
            session_id, "classifying", "Analysiere die Anfrage..."
        )

        context_name, parties_info = await self._context_resolver.get_context_info(
            session.context_id
        )

        conversation_history = format_session_history(session.messages)

        classifier_output = await self._query_classifier.execute(
            QueryClassifierInput(
                query=content,
                context_id=session.context_id,
                context_name=context_name,
                parties_info=parties_info,
                conversation_history=conversation_history,
            )
        )

        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        logger.info(f"Classified message: {classifier_output}")

        if classifier_output.query_type == QueryType.EXPLORATORY:
            return await self._choice_flow.send_choice_prompt(
                session_id=session_id,
                original_query=content,
                detected_parties=classifier_output.detected_parties,
                rag_query=classifier_output.rag_query,
            )

        if classifier_output.query_type == QueryType.META:
            return await self._handle_meta_query(
                session_id=session_id,
                query=content,
                session=session,
            )

        if classifier_output.query_type == QueryType.FACTUAL:
            return await self._factual_query_handler.answer(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties,
                context_id=session.context_id,
            )

        if classifier_output.query_type == QueryType.CLARIFICATION:
            clarification_msg = classifier_output.clarification_question or (
                "Könntest du deine Frage bitte präzisieren?"
            )

            stream_id = str(uuid4())
            await self._streaming.stream_text(
                session_id,
                clarification_msg,
                stream_id,
                "system_message",
                "system",
            )

            await self._streaming.send_chat_message(
                session_id, message=clarification_msg
            )

            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=clarification_msg,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "clarification_needed"}

        fallback_msg = (
            "Ich konnte deine Anfrage nicht einordnen. "
            "Bitte stelle eine Frage zu politischen Themen."
        )

        stream_id = str(uuid4())
        await self._streaming.stream_text(
            session_id,
            fallback_msg,
            stream_id,
            "system_message",
            "system",
        )

        await self._streaming.send_chat_message(session_id, message=fallback_msg)

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
        """Self-contained router for BASELINE mode.

        No exploration option is offered. Content questions go through the
        conversational quick summary path; meta and clarification queries use
        their existing handlers (also conversational).
        """
        await self._streaming.send_thinking(
            session_id, "classifying", "Analysiere die Anfrage..."
        )

        context_name, parties_info = await self._context_resolver.get_context_info(
            session.context_id
        )

        conversation_history = format_session_history(session.messages)

        classifier_output = await self._query_classifier.execute(
            QueryClassifierInput(
                query=content,
                context_id=session.context_id,
                context_name=context_name,
                parties_info=parties_info,
                conversation_history=conversation_history,
            )
        )

        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        logger.info(f"Baseline classified message: {classifier_output}")

        if classifier_output.query_type == QueryType.EXPLORATORY:
            return await self._quick_summary_handler.generate(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties
                or await self._context_resolver.get_default_parties(
                    session.context_id
                ),
                context_id=session.context_id,
                session=session,
            )

        if classifier_output.query_type == QueryType.FACTUAL:
            return await self._factual_query_handler.answer(
                session_id=session_id,
                query=content,
                rag_query=classifier_output.rag_query,
                detected_parties=classifier_output.detected_parties,
                context_id=session.context_id,
            )

        if classifier_output.query_type == QueryType.META:
            return await self._handle_meta_query(
                session_id=session_id,
                query=content,
                session=session,
            )

        if classifier_output.query_type == QueryType.CLARIFICATION:
            clarification_msg = classifier_output.clarification_question or (
                "Könntest du deine Frage bitte präzisieren?"
            )

            stream_id = str(uuid4())
            await self._streaming.stream_text(
                session_id,
                clarification_msg,
                stream_id,
                "system_message",
                "system",
            )

            await self._streaming.send_chat_message(
                session_id, message=clarification_msg
            )

            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=clarification_msg,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "clarification_needed"}

        fallback_msg = (
            "Ich konnte deine Anfrage nicht einordnen. "
            "Bitte stelle eine Frage zu politischen Themen."
        )

        stream_id = str(uuid4())
        await self._streaming.stream_text(
            session_id,
            fallback_msg,
            stream_id,
            "system_message",
            "system",
        )

        await self._streaming.send_chat_message(session_id, message=fallback_msg)

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
        history_lines = format_session_history(session.messages)
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

        llm = self._llm_registry.get(LLMTier.FAST)

        stream_id = str(uuid4())
        full_text = await self._streaming.stream_from_llm(
            session_id=session_id,
            stream_id=stream_id,
            llm_stream=llm.stream(messages=messages, temperature=0.7),
            target_type="quick_summary",
            target_id="meta",
        )

        await self._streaming.send_chat_message(session_id, full_text)

        assistant_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.ASSISTANT,
            content=full_text,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, assistant_msg)

        return {"status": "meta_answered"}
