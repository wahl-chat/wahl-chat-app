# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Per-session in-memory store for current navigation position in the tree."""

from src.guided_exploration.models import NavigationState


class NavigationStateStore:
    """Holds the current ``NavigationState`` per session id.

    The state is rebuilt every time the tree is fully reloaded, so an
    in-memory dict is sufficient — there is no persistence requirement.
    """

    def __init__(self) -> None:
        self._states: dict[str, NavigationState] = {}

    def get(self, session_id: str) -> NavigationState | None:
        return self._states.get(session_id)

    def set(self, session_id: str, state: NavigationState) -> None:
        self._states[session_id] = state

    def clear(self, session_id: str) -> None:
        self._states.pop(session_id, None)
