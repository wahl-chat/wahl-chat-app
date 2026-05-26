# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Lifecycle of an exploration — start, mark, end. No summary plumbing."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.guided_exploration.agents import (
    ExplorationOverviewAgent,
    ExplorationOverviewAgentInput,
    LeafContentGeneratorAgent,
    LeafContentGeneratorInput,
)
from src.guided_exploration.agents.exploration_overview.interface import (
    OverviewAreaInput,
)
from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    BreadcrumbItem,
    BreadcrumbLevel,
    Conversation,
    ExplorationCompleteEvent,
    ExplorationNode,
    ExplorationOverview,
    ExplorationReadyEvent,
    ExplorationTree,
    Message,
    MessageRole,
    MessageType,
    NavigationState,
    NodeStatus,
    SessionMessage,
    SessionMessageType,
    TopicTreeEvent,
)
from src.guided_exploration.models.errors import InsufficientChunksError
from src.guided_exploration.models.exploration import ExplorationStatus
from src.guided_exploration.services.background_tasks import BackgroundTaskRegistry
from src.guided_exploration.services.citation_utils import collect_leaf_citations
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.orchestrator import Orchestrator
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_context import is_study_context

logger = logging.getLogger(__name__)

# Pre-gen leaf timeout: two LLM calls in sequence (structured gen + aspect
# extraction); 45 s leaves headroom for slow-tail latency.
LEAF_PREGEN_TIMEOUT_SECONDS = 45.0


class ExplorationLifecycleHandler:
    """Owns the start/mark/end lifecycle of an exploration.

    The internal start path runs the orchestrator, persists the tree, kicks
    off study pre-gen (when applicable) and seeds navigation state.
    ``mark_explored`` flips the node status; ``end_exploration`` completes
    the exploration and emits ``ExplorationCompleteEvent``.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        context_resolver: ContextResolver,
        navigation_states: NavigationStateStore,
        orchestrator: Orchestrator,
        content_generator: LeafContentGeneratorAgent,
        exploration_overview_agent: ExplorationOverviewAgent,
        pregen_leaf_tasks: dict[tuple[str, str], asyncio.Task],
        background_tasks: BackgroundTaskRegistry,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._context_resolver = context_resolver
        self._navigation_states = navigation_states
        self._orchestrator = orchestrator
        self._content_generator = content_generator
        self._exploration_overview = exploration_overview_agent
        self._pregen_leaf_tasks = pregen_leaf_tasks
        self._background_tasks = background_tasks

    async def start_internal(
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

            if selected_directions:
                exploration_tree.selected_directions = selected_directions

            # Resolve context once; reused by overview + study pre-gen.
            context_name, parties_info = (
                await self._context_resolver.get_context_info(context_id)
            )

            overview = await self._generate_overview(
                query=query,
                tree=exploration_tree,
                context_name=context_name,
                parties_info=parties_info,
            )

            await self._repo.create_exploration(
                session_id,
                query,
                tree=exploration_tree,
                exploration_id=exploration_id,
                overview=overview,
            )

            # Now that the exploration is persisted with its overview,
            # ship tree + overview together so the frontend can render
            # them as a single unit.
            navigation = NavigationState(
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
            await self._sse.send_to_session(
                session_id,
                TopicTreeEvent(
                    exploration_id=exploration_id,
                    tree=exploration_tree,
                    overview=overview,
                    navigation=navigation,
                ),
            )

            leaf_count = len(exploration_tree.root.get_leaf_nodes())
            await self._sse.send_to_session(
                session_id,
                ExplorationReadyEvent(
                    exploration_id=exploration_id,
                    topics_count=len(exploration_tree.root.children),
                    subtopics_count=leaf_count,
                    parties_count=len(parties_info),
                ),
            )

            if low_confidence:
                caveat_text = (
                    "Zu diesem Thema habe ich nur begrenzte Informationen "
                    "gefunden. Die Erkundung zeigt die verfügbaren "
                    "Positionen — es kann sein, dass nicht alle Parteien "
                    "vertreten sind."
                )
                await self._streaming.send_chat_message(session_id, caveat_text)
                caveat_msg = SessionMessage(
                    id=str(uuid4()),
                    type=SessionMessageType.ASSISTANT,
                    content=caveat_text,
                    timestamp=datetime.now(timezone.utc),
                )
                await self._repo.add_session_message(session_id, caveat_msg)

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
                pregen_task = asyncio.create_task(
                    self._pregen_study_leaves(
                        session_id=session_id,
                        exploration_id=exploration_id,
                        tree=exploration_tree,
                        context_name=context_name,
                        parties_info=parties_info,
                    )
                )
                self._background_tasks.register(pregen_task)

            self._navigation_states.set(
                session_id,
                NavigationState(
                    exploration_id=exploration_id,
                    current_path=[],
                    breadcrumb=[
                        BreadcrumbItem(
                            id="root",
                            name="Übersicht",
                            level=BreadcrumbLevel.ROOT,
                        ),
                    ],
                ),
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

            chat_message = (
                "Zu diesem Thema habe ich leider zu wenige Informationen "
                "in den Wahlprogrammen gefunden, um eine Erkundung zu starten. "
                "Versuche es mit einer anderen Frage oder formuliere das "
                "Thema etwas breiter."
            )

            stream_id = str(uuid4())
            await self._streaming.stream_text(
                session_id,
                chat_message,
                stream_id,
                "quick_summary",
                "system",
            )

            await self._streaming.send_chat_message(session_id, chat_message)

            assistant_msg = SessionMessage(
                id=str(uuid4()),
                type=SessionMessageType.ASSISTANT,
                content=chat_message,
                timestamp=datetime.now(timezone.utc),
            )
            await self._repo.add_session_message(session_id, assistant_msg)

            return {"status": "insufficient_data"}

        except Exception:
            logger.exception("Failed to start exploration")
            await self._streaming.send_error(
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
        """Start a new exploration directly (bypasses choice flow)."""
        session = await self._repo.get_session(session_id)
        if not session:
            await self._streaming.send_error(
                session_id,
                "session_not_found",
                "Sitzung nicht gefunden",
            )
            return {"status": "error", "code": "session_not_found"}

        await self._repo.update_session_activity(session_id)

        user_msg = SessionMessage(
            id=str(uuid4()),
            type=SessionMessageType.USER,
            content=query,
            timestamp=datetime.now(timezone.utc),
        )
        await self._repo.add_session_message(session_id, user_msg)

        return await self.start_internal(
            session_id=session_id,
            query=query,
            context_id=context_id,
            parties=parties,
        )

    async def mark_explored(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        """Mark a leaf as explored. No summary is generated."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            await self._streaming.send_error(
                session_id,
                "exploration_not_found",
                "Erkundung nicht gefunden",
            )
            return {"status": "error", "code": "exploration_not_found"}

        await self._mark_leaf_explored(session_id, exploration_id, leaf_id)
        return {"status": "marked_explored", "leaf_id": leaf_id}

    async def end_exploration(
        self,
        session_id: str,
        exploration_id: str,
    ) -> dict:
        """End an exploration. Emits ExplorationCompleteEvent with stats only."""
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

        # Idempotency guard — do not re-send event (S1)
        if exploration.status == ExplorationStatus.COMPLETED:
            return {"status": "already_completed"}

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

        await self._repo.complete_exploration(session_id, exploration_id)

        unexplored = [
            {"id": leaf.id, "name": leaf.name}
            for leaf in all_leaves
            if leaf.id not in explored
        ]

        await self._sse.send_to_session(
            session_id,
            ExplorationCompleteEvent(
                exploration_id=exploration_id,
                stats=stats,
                next_actions={
                    "can_export": False,
                    "can_restart": True,
                    "suggested_topics": unexplored[:3] if unexplored else [],
                },
                unexplored_topics=unexplored,
            ),
        )

        self._navigation_states.clear(session_id)

        return {
            "status": "exploration_ended",
            "exploration_id": exploration_id,
            "stats": stats,
        }

    async def _generate_overview(
        self,
        query: str,
        tree: ExplorationTree,
        context_name: str,
        parties_info: dict[str, PartyInfo],
    ) -> ExplorationOverview | None:
        """Generate the structured overview that ships alongside the tree.

        Best-effort: returns ``None`` when the LLM call fails or the tree
        has no areas. The exploration still works without it.
        """
        areas = [
            OverviewAreaInput(
                name=node.name,
                description=node.description,
                party_ids=list(node.party_ids),
            )
            for node in tree.root.children
        ]
        if not areas:
            return None

        positions_by_party: dict[str, list] = {}
        for position in tree.positions.values():
            positions_by_party.setdefault(position.party_id, []).append(position)

        try:
            return await self._exploration_overview.execute(
                ExplorationOverviewAgentInput(
                    query=query,
                    context_name=context_name,
                    parties=parties_info,
                    areas=areas,
                    positions_by_party=positions_by_party,
                )
            )
        except Exception:
            logger.exception(
                "Exploration overview generation failed; skipping overview"
            )
            return None

    async def _pregen_study_leaves(
        self,
        session_id: str,
        exploration_id: str,
        tree: ExplorationTree,
        context_name: str,
        parties_info: dict[str, PartyInfo],
    ) -> None:
        """Eagerly generate and persist initial content for every leaf in a study."""
        leaves = tree.root.get_leaf_nodes()
        if not leaves:
            return

        logger.info(
            f"Study pre-gen starting: {len(leaves)} leaves "
            f"(exploration={exploration_id})"
        )

        async def gen_and_persist(leaf: ExplorationNode) -> str | None:
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
                    LeafContentGeneratorInput(
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
            )
            await self._repo.save_conversation(
                session_id, exploration_id, conversation
            )
            return leaf.id

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
    ) -> None:
        """Mark a leaf node as explored in the tree.

        Re-fetches the exploration before mutating so concurrent
        navigate / pregen status updates aren't overwritten by a stale
        snapshot.
        """
        fresh = await self._repo.get_exploration(session_id, exploration_id)
        if fresh is None:
            return

        node = fresh.tree.find_node(leaf_id)
        if node is None:
            return

        node.status = NodeStatus.EXPLORED
        await self._repo.update_tree(session_id, exploration_id, fresh.tree)
