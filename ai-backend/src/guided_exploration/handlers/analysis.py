# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Critical-analysis workflow for a leaf — streams analyzer output as a message."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.guided_exploration.agents import AnalyzerAgent, AnalyzerInput
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    Citation,
    ConversationMessageEvent,
    ExtractedPosition,
    ExtractedPositionItem,
    Message,
    MessageRole,
    MessageType,
    ResolvedKnowledge,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService

logger = logging.getLogger(__name__)


class AnalysisHandler:
    """Generates the structured "kritische Analyse" for a leaf and streams it.

    Pulls positions for the leaf, runs them through the analyzer agent, and
    persists/streams the rendered markdown as a regular assistant message.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        context_resolver: ContextResolver,
        navigation_states: NavigationStateStore,
        analyzer: AnalyzerAgent,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._context_resolver = context_resolver
        self._navigation_states = navigation_states
        self._analyzer = analyzer

    async def request_analysis(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        """Run the analyzer and persist its output as an assistant message."""
        session = await self._repo.get_session(session_id)
        if not session:
            return {"status": "error", "code": "session_not_found"}

        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._streaming.send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        conversation = await self._repo.get_conversation(
            session_id, exploration_id, leaf_id
        )
        if not conversation or not conversation.messages:
            await self._streaming.send_error(
                session_id,
                "no_content",
                "Kein Inhalt für Analyse verfügbar",
            )
            return {"status": "error", "code": "no_content"}

        first_msg = conversation.messages[0]
        if not hasattr(first_msg.content, "summary"):
            await self._streaming.send_error(
                session_id,
                "invalid_content",
                "Ungültiger Inhalt für Analyse",
            )
            return {"status": "error", "code": "invalid_content"}

        subtopic_content = first_msg.content

        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)
        if not positions_by_party:
            await self._streaming.send_error(
                session_id,
                "no_knowledge",
                "Kein Wissen für dieses Thema verfügbar",
            )
            return {"status": "error", "code": "no_knowledge"}

        context_name, parties_info = await self._context_resolver.get_context_info(
            session.context_id
        )

        leaf_node = exploration.tree.find_node(leaf_id)
        leaf_name = leaf_node.name if leaf_node else leaf_id

        # Persist a user-side audit message for the analysis request and
        # echo it to the frontend so the chat shows the user's intent.
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

        navigation = self._navigation_states.get(session_id)
        await self._sse.send_to_session(
            session_id,
            ConversationMessageEvent(
                leaf_id=leaf_id,
                message=user_request_msg,
                navigation=navigation,
            ),
        )

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

        await self._streaming.send_thinking(
            session_id, "generating", "Erstelle Analyse..."
        )

        stream_id = str(uuid4())

        try:
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

            await self._streaming.stream_text(
                session_id,
                analysis_markdown,
                stream_id,
                "followup",
                leaf_id,
            )

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

            nav_state = self._navigation_states.get(session_id)
            await self._sse.send_to_session(
                session_id,
                ConversationMessageEvent(
                    leaf_id=leaf_id,
                    message=analysis_message,
                    navigation=nav_state,
                ),
            )
        except Exception:
            logger.exception("Analyzer failed for leaf %s", leaf_id)
            await self._streaming.send_error(
                session_id,
                "LLM_ERROR",
                "Analyse konnte nicht erstellt werden. Bitte erneut versuchen.",
                recoverable=True,
            )
            return {"status": "error", "code": "LLM_ERROR"}

        return {"status": "analysis_generated", "leaf_id": leaf_id}
