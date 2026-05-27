# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Tree navigation — moves between root, topic, and leaf and emits the open events."""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.guided_exploration.agents import (
    LeafContentGeneratorAgent,
    LeafContentGeneratorInput,
)
from src.guided_exploration.agents.party_context import PartyInfo
from src.guided_exploration.api.sse import SSEManager
from src.guided_exploration.models import (
    BreadcrumbItem,
    BreadcrumbLevel,
    Conversation,
    ConversationOpenedEvent,
    Exploration,
    ExplorationNode,
    Message,
    MessageRole,
    MessageType,
    NavigationState,
    NodeStatus,
    SiblingNavigation,
    TopicOverviewEvent,
)
from src.guided_exploration.models.classification import NavigationTarget
from src.guided_exploration.services.citation_utils import (
    collect_leaf_citations,
    extract_used_citations,
)
from src.guided_exploration.services.context_resolver import ContextResolver
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.streaming import StreamingService
from src.guided_exploration.services.study_exposure import StudyExposureLogger

logger = logging.getLogger(__name__)


class NavigationHandler:
    """Handles position changes within the topic tree.

    Keeps the in-memory navigation state in sync with each user-driven move
    and emits the appropriate "opened" event (topic overview vs. leaf
    conversation). Lazy content generation for leaves happens here too;
    pre-gen tasks are awaited via the shared registry to avoid duplicate LLM
    calls.
    """

    def __init__(
        self,
        repo: SessionRepository,
        sse: SSEManager,
        streaming: StreamingService,
        context_resolver: ContextResolver,
        navigation_states: NavigationStateStore,
        content_generator: LeafContentGeneratorAgent,
        pregen_leaf_tasks: dict[tuple[str, str], asyncio.Task],
        study_exposure: StudyExposureLogger,
    ) -> None:
        self._repo = repo
        self._sse = sse
        self._streaming = streaming
        self._context_resolver = context_resolver
        self._navigation_states = navigation_states
        self._content_generator = content_generator
        self._pregen_leaf_tasks = pregen_leaf_tasks
        self._study_exposure = study_exposure

    async def navigate(
        self,
        session_id: str,
        exploration_id: str,
        target_path: list[str],
    ) -> dict:
        """Move to ``target_path`` (root if empty) and emit the open event."""
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

        tree = exploration.tree

        if len(target_path) == 0:
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
            return {"status": "at_root"}

        target_id = target_path[-1]
        node = tree.find_node(target_id)
        if not node:
            await self._streaming.send_error(
                session_id,
                "node_not_found",
                f"Knoten '{target_id}' nicht gefunden",
            )
            return {"status": "error", "code": "node_not_found"}

        if node.is_leaf:
            context_name, parties_info = (
                await self._context_resolver.get_context_info(session.context_id)
            )

            _, navigation = await self.navigate_to_leaf(
                session_id,
                exploration,
                leaf_id=node.id,
                leaf_name=node.name,
                leaf_parties=node.party_ids,
                context_name=context_name,
                parties_info=parties_info,
            )

            self._navigation_states.set(session_id, navigation)
            return {"status": "navigated", "path": target_path}

        navigation = await self.navigate_to_branch(
            session_id,
            exploration,
            node,
        )
        self._navigation_states.set(session_id, navigation)
        return {"status": "navigated", "path": target_path}

    async def navigate_to_branch(
        self,
        session_id: str,
        exploration: Exploration,
        node: ExplorationNode,
    ) -> NavigationState:
        """Send a TopicOverviewEvent for an interior tree node."""
        path = exploration.tree.root.get_path_to(node.id) or []
        breadcrumb = [
            BreadcrumbItem(
                id="root",
                name="Übersicht",
                level=BreadcrumbLevel.ROOT,
            ),
        ]
        for p in path[1:]:
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

    async def navigate_to_leaf(
        self,
        session_id: str,
        exploration: Exploration,
        leaf_id: str,
        leaf_name: str,
        leaf_parties: list[str],
        context_name: str,
        parties_info: dict[str, PartyInfo],
    ) -> tuple[Conversation, NavigationState]:
        """Open a leaf — generate or reuse content, persist, emit opened event."""
        # B2: Check the pre-gen registry FIRST to avoid a race where the task
        # completes and the finally-pop removes the key between get_conversation
        # and the registry check — which would cause a duplicate LLM call.
        pregen_task = self._pregen_leaf_tasks.get((exploration.id, leaf_id))
        if pregen_task is not None:
            if not pregen_task.done():
                await self._streaming.send_thinking(
                    session_id, "generating", "Bereite Inhalte vor..."
                )
            try:
                await pregen_task
            except Exception:
                logger.warning(
                    "pregen task failed for leaf %s, falling back to lazy path",
                    leaf_id,
                    exc_info=True,
                )

        existing_conversation = await self._repo.get_conversation(
            session_id, exploration.id, leaf_id
        )

        positions_by_party = exploration.tree.get_positions_by_party(leaf_id)

        node_path = exploration.tree.root.get_path_to(leaf_id) or []
        current_path = [n.id for n in node_path[1:]]
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

        content = None

        if existing_conversation and existing_conversation.messages:
            conversation = existing_conversation

            initial_msg = existing_conversation.messages[0]
            if hasattr(initial_msg.content, "summary"):
                content = initial_msg.content
                # Cached content is delivered via ConversationOpenedEvent below,
                # so no re-streaming is needed. Streaming the summary again would
                # leave a stale buffer on the client that renders a duplicate
                # summary below the already-committed structured message.
        else:
            await self._streaming.send_thinking(
                session_id, "generating", "Bereite Inhalte vor..."
            )

            path = current_path

            leaf_citations = collect_leaf_citations(positions_by_party)
            content = await self._content_generator.execute(
                LeafContentGeneratorInput(
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

            stream_id = str(uuid4())
            await self._streaming.stream_text(
                session_id,
                content.summary,
                stream_id,
                "initial_content",
                leaf_id,
                section="summary",
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
                leaf_id=leaf_id,
                messages=[initial_message],
            )

            await self._repo.save_conversation(
                session_id,
                exploration.id,
                conversation,
            )

        # Log Information-Exposure for the leaf intro the participant just
        # opened. We parse `[id]` markers out of party_positions[*].content
        # (the only field where the leaf_content_generator inlines citations) and
        # match against the leaf's full citation pool. Cached and freshly-
        # generated branches both end up here; dedup is handled at storage.
        if content is not None and content.party_positions:
            initial_text = "\n".join(p.content for p in content.party_positions)
            used_citations = extract_used_citations(initial_text, content.citations)
            await self._study_exposure.log(session_id, used_citations)

        # Promote node status to 'started' unless the user already finished it.
        # Transitions: pending/loaded -> started. 'explored' is terminal.
        leaf_node = exploration.tree.find_node(leaf_id)
        if leaf_node is not None and leaf_node.status in {
            NodeStatus.PENDING,
            NodeStatus.LOADED,
        }:
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

        # Surface the latest answer's chips on reopen: walk newest-first and
        # prefer a follow-up's persisted suggested_followups, falling back to
        # the initial content's suggested_questions. First non-empty wins.
        suggested_questions: list[str] = []
        for msg in reversed(conversation.messages):
            if msg.role != MessageRole.ASSISTANT:
                continue
            from_followups = msg.suggested_followups or []
            from_content = getattr(msg.content, "suggested_questions", None) or []
            q = from_followups or from_content
            if q:
                suggested_questions = q
                break

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

    async def handle_navigation_command(
        self,
        session_id: str,
        exploration_id: str,
        exploration: Exploration,
        current_leaf_id: str,
        navigation_target: NavigationTarget | None,
    ) -> dict:
        """Resolve a high-level navigation command into a target path and navigate."""
        tree = exploration.tree

        current_state = self._navigation_states.get(session_id)
        current_path_list = current_state.current_path if current_state else []

        target_path: list[str] = []

        if navigation_target == NavigationTarget.OVERVIEW:
            target_path = []

        elif navigation_target == NavigationTarget.BACK:
            if len(current_path_list) > 1:
                target_path = current_path_list[:-1]
            else:
                target_path = []

        elif navigation_target in (
            NavigationTarget.NEXT,
            NavigationTarget.PREVIOUS,
        ):
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
                            await self._streaming.send_error(
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
                await self._streaming.send_error(
                    session_id,
                    "navigation_not_applicable",
                    "Navigation nicht möglich. Wählen Sie zuerst ein Unterthema.",
                    recoverable=True,
                )
                return {"status": "not_applicable"}

        else:
            # Classifier returned NAVIGATION_COMMAND without a resolved target.
            # Surface as a recoverable error instead of silently going to root.
            await self._streaming.send_error(
                session_id,
                "navigation_invalid",
                "Navigation nicht erkannt. Bitte präziser formulieren.",
                recoverable=True,
            )
            return {"status": "not_applicable"}

        return await self.navigate(session_id, exploration_id, target_path)
