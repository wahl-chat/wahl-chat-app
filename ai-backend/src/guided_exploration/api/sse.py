# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""SSE connection management for guided exploration using aiohttp-sse."""

import asyncio
import logging
from uuid import uuid4

from aiohttp import web
from aiohttp_sse import sse_response

from src.guided_exploration.models import ConnectedEvent, SessionClaimedEvent, SSEEvent

logger = logging.getLogger(__name__)


class SSEConnection:
    """Manages a single SSE connection."""

    def __init__(self, session_id: str, client_id: str):
        self.session_id = session_id
        self.client_id = client_id
        self.connection_id = str(uuid4())
        self.queue: asyncio.Queue[SSEEvent | None] = asyncio.Queue()
        self._closed = False

    async def send(self, event: SSEEvent) -> None:
        """Queue an event for sending."""
        if not self._closed:
            await self.queue.put(event)

    async def close(self) -> None:
        """Signal connection close."""
        self._closed = True
        await self.queue.put(None)

    @property
    def is_closed(self) -> bool:
        return self._closed


class SSEManager:
    """
    Manages active SSE connections per session.

    A `client_id` (per browser tab) identifies the caller. Reconnects from
    the same `client_id` are silent replaces — covers React StrictMode
    remounts and EventSource auto-reconnects without disrupting the user.
    A different `client_id` for the same session is a real cross-tab claim
    and emits `SessionClaimedEvent` on the old connection.
    """

    def __init__(self) -> None:
        self._connections: dict[str, SSEConnection] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, client_id: str) -> SSEConnection:
        """
        Register a new connection. Same-client reconnects silently replace
        the old connection; different-client connects claim the session.
        """
        async with self._lock:
            if session_id in self._connections:
                old_conn = self._connections[session_id]
                if old_conn.client_id == client_id:
                    await old_conn.close()
                    logger.info(
                        f"SSE same-client reconnect: session={session_id} "
                        f"client={client_id}"
                    )
                else:
                    await old_conn.send(
                        SessionClaimedEvent(
                            session_id=session_id,
                            message="Session claimed by another connection",
                        )
                    )
                    await old_conn.close()
                    logger.info(
                        f"Session {session_id} claimed by client={client_id} "
                        f"(was client={old_conn.client_id})"
                    )

            conn = SSEConnection(session_id, client_id)
            self._connections[session_id] = conn
            logger.info(f"SSE connected: session={session_id} client={client_id}")
            return conn

    async def disconnect(self, session_id: str, connection_id: str) -> None:
        """Remove connection if it matches current."""
        async with self._lock:
            conn = self._connections.get(session_id)
            if conn and conn.connection_id == connection_id:
                del self._connections[session_id]
                logger.info(f"SSE disconnected: {session_id}")

    async def send_to_session(self, session_id: str, event: SSEEvent) -> bool:
        """Send event to session. Returns False if not connected."""
        conn = self._connections.get(session_id)
        if conn and not conn.is_closed:
            logger.debug(f"SSE -> {event.type}: session={session_id}")
            await conn.send(event)
            return True
        reason = (
            "no_connection"
            if conn is None
            else "connection_closed"
        )
        logger.warning(
            f"SSE DROP {event.type} session={session_id} reason={reason}"
        )
        return False

    def get_connection(self, session_id: str) -> SSEConnection | None:
        """Get connection for session."""
        return self._connections.get(session_id)


async def sse_handler(
    request: web.Request,
    session_id: str,
    client_id: str,
    manager: SSEManager,
) -> web.StreamResponse:
    """
    aiohttp SSE endpoint handler.

    `client_id` identifies the browser tab (sent as `?client_id=` query
    param). Same-client reconnects are silent; different-client triggers
    `session_claimed` on the old connection.
    """
    conn = await manager.connect(session_id, client_id)

    async with sse_response(request) as resp:
        # Send connected event
        try:
            await resp.send(
                ConnectedEvent(session_id=session_id).model_dump_json(),
                event="connected",
            )
        except (ConnectionResetError, ConnectionAbortedError):
            logger.debug(f"SSE connection closed immediately: {session_id}")
            await manager.disconnect(session_id, conn.connection_id)
            return resp

        try:
            while True:
                event = await conn.queue.get()

                if event is None:  # Close sentinel
                    break

                try:
                    await resp.send(event.model_dump_json(), event=event.type)
                except (ConnectionResetError, ConnectionAbortedError):
                    logger.debug(f"SSE connection closed by client: {session_id}")
                    break
        except asyncio.CancelledError:
            logger.debug(f"SSE cancelled: {session_id}")
        except (ConnectionResetError, ConnectionAbortedError):
            logger.debug(f"SSE connection reset: {session_id}")
        finally:
            await manager.disconnect(session_id, conn.connection_id)

    return resp


# Global instance
_sse_manager: SSEManager | None = None


def get_sse_manager() -> SSEManager:
    """Get or create global SSE manager."""
    global _sse_manager
    if _sse_manager is None:
        _sse_manager = SSEManager()
    return _sse_manager
