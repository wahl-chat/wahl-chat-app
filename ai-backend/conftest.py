# SPDX-FileCopyrightText: 2025 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Root pytest conftest for ai-backend.

Provides:
- pytest_configure: sets API_NAME env var so V1 test_websocket_app.py can be
  collected (it calls load_env() at module level; without API_NAME it raises
  at collection time).
- pytest_collection_modifyitems: marks all tests in test_websocket_app.py as
  skipped — it is a Socket.IO integration suite superseded by test_chat_sse.py
  once the FastAPI/SSE migration is complete.
"""

import os
import pytest


def pytest_configure(config):
    """Set required env vars before test collection."""
    # V1 test_websocket_app.py calls load_env() at import time which requires
    # API_NAME=wahl-chat-api. Set it here so collection does not fail.
    os.environ.setdefault("API_NAME", "wahl-chat-api")


def pytest_collection_modifyitems(items):
    """Skip the V1 Socket.IO integration tests — plan 01-06 rewrites them as SSE tests."""
    skip_marker = pytest.mark.skip(
        reason=(
            "V1 Socket.IO integration suite: requires a running aiohttp server. "
            "Superseded by tests/test_chat_sse.py in plan 01-06. "
            "See RESEARCH.md Pitfall 4."
        )
    )
    for item in items:
        if "test_websocket_app" in item.nodeid:
            item.add_marker(skip_marker)
