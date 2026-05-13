# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Facade for guided exploration — public module interface.

Pure dispatch: every public method is a one-line delegate to the right
collaborator. Construction lives in ``composition.build_facade``.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from src.guided_exploration.handlers.analysis import AnalysisHandler
    from src.guided_exploration.handlers.choice_flow import ChoiceFlowHandler
    from src.guided_exploration.handlers.exploration_lifecycle import (
        ExplorationLifecycleHandler,
    )
    from src.guided_exploration.handlers.inbound_router import InboundRouter
    from src.guided_exploration.handlers.leaf_conversation import (
        LeafConversationHandler,
    )
    from src.guided_exploration.handlers.navigation import NavigationHandler
    from src.guided_exploration.models import SessionInfo, SessionMode
    from src.guided_exploration.services.background_tasks import (
        BackgroundTaskRegistry,
    )
    from src.guided_exploration.services.session_service import SessionService
    from src.guided_exploration.services.study_exposure import (
        StudyExposureLogger,
    )


class GuidedExplorationFacade:
    """Thin public interface for the guided exploration module."""

    def __init__(
        self,
        *,
        session_service: "SessionService",
        inbound_router: "InboundRouter",
        choice_flow: "ChoiceFlowHandler",
        exploration_lifecycle: "ExplorationLifecycleHandler",
        navigation_handler: "NavigationHandler",
        leaf_conversation_handler: "LeafConversationHandler",
        analysis_handler: "AnalysisHandler",
        background_tasks: "BackgroundTaskRegistry",
        study_exposure: "StudyExposureLogger",
    ) -> None:
        self._session_service = session_service
        self._inbound_router = inbound_router
        self._choice_flow = choice_flow
        self._exploration_lifecycle = exploration_lifecycle
        self._navigation_handler = navigation_handler
        self._leaf_conversation_handler = leaf_conversation_handler
        self._analysis_handler = analysis_handler
        self._background_tasks = background_tasks
        self._study_exposure = study_exposure

    def set_study_exposure_logger(
        self,
        logger_fn: "Callable[[str, list[str]], Awaitable[None]]",
    ) -> None:
        self._study_exposure.register(logger_fn)

    async def create_session(
        self,
        context_id: str,
        user_id: str | None = None,
        mode: "SessionMode | None" = None,
        max_claims_per_party: int | None = None,
    ) -> "SessionInfo":
        from src.guided_exploration.models import SessionMode

        return await self._session_service.create(
            context_id=context_id,
            user_id=user_id,
            mode=mode if mode is not None else SessionMode.GUIDED,
            max_claims_per_party=max_claims_per_party,
        )

    async def get_session(self, session_id: str) -> dict | None:
        return await self._session_service.get_resume_state(session_id)

    async def list_explorations(self, session_id: str) -> list[dict]:
        return await self._session_service.list_explorations(session_id)

    async def get_exploration(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        return await self._session_service.get_exploration(
            session_id, exploration_id
        )

    async def get_exploration_conversations(
        self, session_id: str, exploration_id: str
    ) -> list:
        return await self._session_service.get_conversations(
            session_id, exploration_id
        )

    async def get_knowledge_base(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        return await self._session_service.get_knowledge_base(
            session_id, exploration_id
        )

    async def handle_message(
        self,
        session_id: str,
        content: str,
        exploration_context: dict | None = None,
    ) -> dict:
        return await self._inbound_router.handle_message(
            session_id, content, exploration_context
        )

    async def handle_direction_choice(
        self,
        session_id: str,
        query_id: str,
        directions: list[dict],
    ) -> dict:
        return await self._choice_flow.handle_direction_choice(
            session_id, query_id, directions
        )

    async def handle_choice(
        self,
        session_id: str,
        query_id: str,
        choice: Literal["explore", "summary"],
        parties: list[str] | None = None,
    ) -> dict:
        return await self._choice_flow.handle_choice(
            session_id, query_id, choice, parties
        )

    async def start_exploration(
        self,
        session_id: str,
        query: str,
        context_id: str,
        parties: list[str],
    ) -> dict:
        return await self._exploration_lifecycle.start_exploration(
            session_id=session_id,
            query=query,
            context_id=context_id,
            parties=parties,
        )

    async def navigate(
        self,
        session_id: str,
        exploration_id: str,
        target_path: list[str],
    ) -> dict:
        return await self._navigation_handler.navigate(
            session_id, exploration_id, target_path
        )

    async def mark_explored(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        return await self._exploration_lifecycle.mark_explored(
            session_id, exploration_id, leaf_id
        )

    async def request_analysis(
        self,
        session_id: str,
        exploration_id: str,
        leaf_id: str,
    ) -> dict:
        return await self._analysis_handler.request_analysis(
            session_id, exploration_id, leaf_id
        )

    async def end_exploration(
        self,
        session_id: str,
        exploration_id: str,
    ) -> dict:
        return await self._exploration_lifecycle.end_exploration(
            session_id, exploration_id
        )

    async def cleanup(self) -> None:
        await self._background_tasks.cleanup()
