# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Unit tests for SSE infrastructure."""

import asyncio

import pytest

from src.guided_exploration.api import SSEManager
from src.guided_exploration.models import ConnectedEvent


@pytest.mark.asyncio
async def test_sse_connection_basic():
    """Test basic SSE connection creation."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")

    assert conn is not None
    assert conn.session_id == "session-1"
    assert conn.client_id == "client-A"
    assert conn.connection_id is not None
    assert not conn.is_closed
    assert manager.get_connection("session-1") is conn


@pytest.mark.asyncio
async def test_sse_send_event():
    """Test sending events to a session."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")

    event = ConnectedEvent(session_id="session-1")
    result = await manager.send_to_session("session-1", event)

    assert result is True

    # Verify the event was queued
    received = await conn.queue.get()
    assert received.type == "connected"
    assert received.session_id == "session-1"


@pytest.mark.asyncio
async def test_sse_send_to_nonexistent_session():
    """Test sending to a session that doesn't exist."""
    manager = SSEManager()

    event = ConnectedEvent(session_id="nonexistent")
    result = await manager.send_to_session("nonexistent", event)

    assert result is False


@pytest.mark.asyncio
async def test_sse_session_claiming_different_client():
    """A connection from a different client_id claims the session."""
    manager = SSEManager()

    conn1 = await manager.connect("session-1", "client-A")
    assert manager.get_connection("session-1") is conn1

    conn2 = await manager.connect("session-1", "client-B")
    assert manager.get_connection("session-1") is conn2
    assert conn2 is not conn1

    # Old connection should receive session_claimed event and be closed
    claimed_event = await conn1.queue.get()
    assert claimed_event.type == "session_claimed"
    assert claimed_event.session_id == "session-1"

    # Old connection should receive close sentinel
    close_sentinel = await conn1.queue.get()
    assert close_sentinel is None
    assert conn1.is_closed


@pytest.mark.asyncio
async def test_sse_same_client_silent_replace():
    """Same client_id reconnecting closes old connection without claim event."""
    manager = SSEManager()

    conn1 = await manager.connect("session-1", "client-A")
    conn2 = await manager.connect("session-1", "client-A")

    assert manager.get_connection("session-1") is conn2
    assert conn2 is not conn1

    # Old connection should be closed but receive no claim event
    sentinel = await conn1.queue.get()
    assert sentinel is None
    assert conn1.is_closed
    # No claim event was queued — only the close sentinel
    assert conn1.queue.empty()


@pytest.mark.asyncio
async def test_sse_disconnect():
    """Test disconnecting a connection."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")
    connection_id = conn.connection_id

    await manager.disconnect("session-1", connection_id)

    assert manager.get_connection("session-1") is None


@pytest.mark.asyncio
async def test_sse_disconnect_wrong_connection_id():
    """Test that disconnect with wrong connection_id is ignored."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")

    # Try to disconnect with wrong connection_id
    await manager.disconnect("session-1", "wrong-id")

    # Connection should still exist
    assert manager.get_connection("session-1") is conn


@pytest.mark.asyncio
async def test_sse_connection_close():
    """Test closing a connection."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")
    await conn.close()

    assert conn.is_closed

    # Verify close sentinel was sent
    sentinel = await conn.queue.get()
    assert sentinel is None


@pytest.mark.asyncio
async def test_sse_send_to_closed_connection():
    """Test that sending to a closed connection is ignored."""
    manager = SSEManager()

    conn = await manager.connect("session-1", "client-A")
    await conn.close()

    # This should not raise and should not queue
    await conn.send(ConnectedEvent(session_id="session-1"))

    # Queue should only have the close sentinel
    sentinel = await conn.queue.get()
    assert sentinel is None

    # Queue should be empty (no new event was added)
    assert conn.queue.empty()


@pytest.mark.asyncio
async def test_sse_multiple_sessions():
    """Test managing multiple sessions concurrently."""
    manager = SSEManager()

    conn1 = await manager.connect("session-1", "client-A")
    conn2 = await manager.connect("session-2", "client-B")
    conn3 = await manager.connect("session-3", "client-C")

    assert manager.get_connection("session-1") is conn1
    assert manager.get_connection("session-2") is conn2
    assert manager.get_connection("session-3") is conn3

    # Send to each session
    await manager.send_to_session("session-1", ConnectedEvent(session_id="session-1"))
    await manager.send_to_session("session-2", ConnectedEvent(session_id="session-2"))

    # Verify correct routing
    event1 = await conn1.queue.get()
    event2 = await conn2.queue.get()

    assert event1.session_id == "session-1"
    assert event2.session_id == "session-2"
    assert conn3.queue.empty()


@pytest.mark.asyncio
async def test_sse_concurrent_operations():
    """Test concurrent connect/send operations."""
    manager = SSEManager()

    async def connect_and_send(session_id: str):
        conn = await manager.connect(session_id, f"client-{session_id}")
        await manager.send_to_session(session_id, ConnectedEvent(session_id=session_id))
        return conn

    # Run multiple operations concurrently
    results = await asyncio.gather(
        connect_and_send("session-1"),
        connect_and_send("session-2"),
        connect_and_send("session-3"),
    )

    assert len(results) == 3
    for i, conn in enumerate(results, 1):
        event = await conn.queue.get()
        assert event.session_id == f"session-{i}"
