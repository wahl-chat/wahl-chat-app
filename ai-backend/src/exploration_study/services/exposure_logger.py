# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Information Exposure logger for the study.

The guided exploration facade calls into this module after every citation
extraction in a study session. Each cited position id is merged into the
participant's ``condition.positions_encountered`` list via the study
session repository.

The module-level ``log_study_exposure`` function is registered with the
guided exploration facade at startup via ``set_study_exposure_logger``.
The boundary keeps ``guided_exploration`` free of any hard dependency on
``exploration_study`` — the guided facade just calls whatever callback
was injected.
"""

from __future__ import annotations

import logging

from src.exploration_study.services.session_repository import (
    get_session_repository,
)

logger = logging.getLogger(__name__)


async def log_study_exposure(chat_id: str, position_ids: list[str]) -> None:
    """
    Merge cited position ids into the study session's
    ``positions_encountered`` list.

    Args:
        chat_id: The guided exploration session id (same value stored on
            ``StudySession.condition.chat_id`` when the task started).
        position_ids: Master position ids that were cited by the LLM in
            the most recent response.
    """
    if not position_ids:
        return

    try:
        repo = get_session_repository()
        await repo.append_positions_encountered(chat_id, position_ids)
    except Exception as e:
        # Logging failures must never break the user-facing response.
        logger.warning(
            f"log_study_exposure failed for chat_id={chat_id}: "
            f"{type(e).__name__}: {e}"
        )
