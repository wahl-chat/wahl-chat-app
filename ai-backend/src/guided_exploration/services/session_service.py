# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Session-level read/write surface used by the facade.

Holds the business logic that previously lived inline in
``GuidedExplorationFacade`` for session creation, resume payload
assembly, and exploration view-building.
"""

import logging

from src.guided_exploration.models import SessionInfo, SessionMode
from src.guided_exploration.services.navigation_state_store import (
    NavigationStateStore,
)
from src.guided_exploration.services.session_repository import SessionRepository

logger = logging.getLogger(__name__)


class SessionService:
    """Read/write surface for session and exploration data."""

    def __init__(
        self,
        repo: SessionRepository,
        navigation_states: NavigationStateStore,
    ) -> None:
        self._repo = repo
        self._navigation_states = navigation_states

    async def create(
        self,
        context_id: str,
        user_id: str | None = None,
        mode: SessionMode = SessionMode.GUIDED,
        max_claims_per_party: int | None = None,
    ) -> SessionInfo:
        """Create a new session and return the connection-info envelope."""
        session = await self._repo.create_session(
            context_id=context_id,
            user_id=user_id,
            mode=mode,
            max_claims_per_party=max_claims_per_party,
        )

        logger.info(
            f"Created session: {session.id} with mode={mode.value} "
            f"max_claims_per_party={max_claims_per_party}"
        )

        return SessionInfo(
            session_id=session.id,
            stream_url=f"/api/v1/guided-exploration/sessions/{session.id}/stream",
            active_exploration=None,
        )

    async def get_resume_state(self, session_id: str) -> dict | None:
        """Assemble the full resume payload for an existing session."""
        session = await self._repo.get_session(session_id)
        if not session:
            return None

        await self._repo.update_session_activity(session_id)

        active_exploration = await self._repo.get_active_exploration(session_id)
        messages = [msg.model_dump(mode="json") for msg in session.messages]
        explorations = await self._repo.list_explorations(session_id)

        result: dict = {
            "session_id": session_id,
            "context_id": session.context_id,
            "user_id": session.user_id,
            "active_exploration": None,
            "navigation_state": None,
            "messages": messages,
            "explorations": explorations,
        }

        if active_exploration:
            result["active_exploration"] = {
                "id": active_exploration.id,
                "original_query": active_exploration.original_query,
                "status": active_exploration.status.value,
                "tree": active_exploration.tree.model_dump(mode="json"),
            }
            nav_state = self._navigation_states.get(session_id)
            if nav_state:
                result["navigation_state"] = nav_state.model_dump(mode="json")

        return result

    async def list_explorations(self, session_id: str) -> list[dict]:
        """List all explorations for a session."""
        return await self._repo.list_explorations(session_id)

    async def get_exploration(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        """Get a specific exploration with its full tree."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            return None

        return {
            "id": exploration.id,
            "original_query": exploration.original_query,
            "status": exploration.status.value,
            "tree": exploration.tree.model_dump(mode="json"),
            "created_at": exploration.created_at.isoformat()
            if exploration.created_at
            else None,
        }

    async def get_conversations(
        self,
        session_id: str,
        exploration_id: str,
    ) -> list:
        """List all leaf conversations for an exploration."""
        return await self._repo.list_conversations(session_id, exploration_id)

    async def get_knowledge_base(
        self, session_id: str, exploration_id: str
    ) -> dict | None:
        """Get the knowledge base for an exploration (debug surface)."""
        exploration = await self._repo.get_exploration(session_id, exploration_id)
        if not exploration:
            return None

        return {
            "exploration_id": exploration_id,
            "positions": {
                cid: c.model_dump(mode="json")
                for cid, c in exploration.tree.positions.items()
            },
        }
