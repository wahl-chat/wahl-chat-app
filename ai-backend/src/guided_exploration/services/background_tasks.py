# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Registry for fire-and-forget asyncio tasks.

Used to track tasks created via ``asyncio.create_task`` so they can be
cancelled gracefully on server shutdown. Completed tasks remove
themselves via ``add_done_callback``.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class BackgroundTaskRegistry:
    """Tracks fire-and-forget tasks for graceful cleanup."""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()

    def register(self, task: asyncio.Task) -> None:
        """Add a task and wire its self-removal callback."""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def tasks(self) -> set[asyncio.Task]:
        """Direct access for handlers that already manage their own
        completion callbacks (e.g., navigation pre-gen tasks)."""
        return self._tasks

    async def cleanup(self) -> None:
        """Cancel all pending tasks and await their completion."""
        pending = {t for t in self._tasks if not t.done()}
        if pending:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
        logger.info(
            f"BackgroundTaskRegistry cleanup: cancelled {len(pending)} tasks"
        )
