# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Records cited position ids for the study's Information-Exposure metric."""

import logging
from collections.abc import Awaitable, Callable

from src.guided_exploration.models import Citation
from src.guided_exploration.services.session_repository import SessionRepository
from src.guided_exploration.services.study_context import is_study_context

logger = logging.getLogger(__name__)

ExposureCallback = Callable[[str, list[str]], Awaitable[None]]


class StudyExposureLogger:
    """Forwards cited position ids to an externally-registered callback.

    Silent no-op for non-study sessions and when no callback has been
    registered. Failures are logged but never propagate to the user-facing
    response — the metric is auxiliary, not on the critical path.
    """

    def __init__(self, repo: SessionRepository) -> None:
        self._repo = repo
        self._callback: ExposureCallback | None = None

    def register(self, callback: ExposureCallback) -> None:
        self._callback = callback
        logger.info("Study exposure logger registered")

    async def log(
        self,
        session_id: str,
        citations: list[Citation],
    ) -> None:
        if self._callback is None or not citations:
            return

        session = await self._repo.get_session(session_id)
        if not session or not is_study_context(session.context_id):
            return

        position_ids: list[str] = []
        seen: set[str] = set()
        for c in citations:
            if c.id and c.id not in seen:
                seen.add(c.id)
                position_ids.append(c.id)
        if not position_ids:
            return

        try:
            await self._callback(session_id, position_ids)
        except Exception as e:
            logger.warning(
                f"Study exposure logger failed for session {session_id}: {e}"
            )
