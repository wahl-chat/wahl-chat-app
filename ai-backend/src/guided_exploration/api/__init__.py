# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""API module for guided exploration SSE connections and REST routes."""

from src.guided_exploration.api.dtos import (
    CreateSessionRequest,
    CreateSessionResponse,
    NavigateRequest,
    RequestAnalysisRequest,
    ResumeSessionResponse,
    SendMessageRequest,
    SubmitChoiceRequest,
)
from src.guided_exploration.api.routes import setup_guided_exploration_routes
from src.guided_exploration.api.sse import SSEManager, get_sse_manager

__all__ = [
    # SSE
    "SSEManager",
    "get_sse_manager",
    # Routes
    "setup_guided_exploration_routes",
    # DTOs
    "CreateSessionRequest",
    "CreateSessionResponse",
    "NavigateRequest",
    "RequestAnalysisRequest",
    "ResumeSessionResponse",
    "SendMessageRequest",
    "SubmitChoiceRequest",
]
