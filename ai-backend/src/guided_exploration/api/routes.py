# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""REST API routes for guided exploration."""

import logging

from aiohttp import web

from src.guided_exploration.api.dtos import (
    CreateSessionRequest,
    CreateSessionResponse,
    EndExplorationRequest,
    MarkExploredRequest,
    NavigateRequest,
    RequestAnalysisRequest,
    ResumeSessionResponse,
    SendMessageRequest,
    SubmitChoiceRequest,
    SubmitDirectionChoiceRequest,
)
from src.guided_exploration.api.sse import get_sse_manager, sse_handler

logger = logging.getLogger(__name__)

# Route prefix for guided exploration API
ROUTE_PREFIX = "/api/v1/guided-exploration"


def get_facade():
    """Get the facade instance (lazy import to avoid circular imports)."""
    from src.guided_exploration.facade import get_facade as _get_facade

    return _get_facade()


async def create_session(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions
    Create a new guided exploration session.
    """
    try:
        body = await request.json()
        req = CreateSessionRequest(**body)
    except Exception:
        req = CreateSessionRequest()

    facade = get_facade()
    session_info = await facade.create_session(
        context_id=req.context_id,
        user_id=req.user_id,
    )

    response = CreateSessionResponse(
        session_id=session_info.session_id,
        stream_url=f"{ROUTE_PREFIX}/sessions/{session_info.session_id}/stream",
        context_id=req.context_id,
    )

    return web.json_response(response.model_dump(), status=201)


async def get_session(request: web.Request) -> web.Response:
    """
    GET /api/v1/guided-exploration/sessions/{session_id}
    Resume/get an existing session.
    """
    session_id = request.match_info["session_id"]

    facade = get_facade()
    session_data = await facade.get_session(session_id)

    if session_data is None:
        return web.json_response(
            {"error": "session_not_found", "message": "Session not found"},
            status=404,
        )

    response = ResumeSessionResponse(
        session_id=session_id,
        stream_url=f"{ROUTE_PREFIX}/sessions/{session_id}/stream",
        context_id=session_data.get("context_id", "bundestagswahl-2025"),
        active_exploration=session_data.get("active_exploration"),
        navigation_state=session_data.get("navigation_state"),
        messages=session_data.get("messages", []),
        explorations=session_data.get("explorations", []),
    )

    return web.json_response(response.model_dump())


async def stream_session(request: web.Request) -> web.StreamResponse:
    """
    GET /api/v1/guided-exploration/sessions/{session_id}/stream
    SSE stream for real-time updates.
    """
    session_id = request.match_info["session_id"]
    manager = get_sse_manager()
    return await sse_handler(request, session_id, manager)


async def list_explorations(request: web.Request) -> web.Response:
    """
    GET /api/v1/guided-exploration/sessions/{session_id}/explorations
    List all explorations for a session.
    """
    session_id = request.match_info["session_id"]

    facade = get_facade()
    explorations = await facade.list_explorations(session_id)

    return web.json_response({"explorations": explorations})


async def get_exploration(request: web.Request) -> web.Response:
    """
    GET /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}
    Get a specific exploration with its full tree.
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    facade = get_facade()
    exploration = await facade.get_exploration(session_id, exploration_id)

    if exploration is None:
        return web.json_response(
            {"error": "exploration_not_found", "message": "Exploration not found"},
            status=404,
        )

    return web.json_response(exploration)


async def get_knowledge_base(request: web.Request) -> web.Response:
    """
    GET /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}/knowledge-base
    Get the knowledge base for an exploration (for debugging).
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    facade = get_facade()
    knowledge_base = await facade.get_knowledge_base(session_id, exploration_id)

    if knowledge_base is None:
        return web.json_response(
            {"error": "exploration_not_found", "message": "Exploration not found"},
            status=404,
        )

    return web.json_response(knowledge_base)


async def send_message(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/message
    Send a message in the session. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = SendMessageRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.handle_message(
        session_id=session_id,
        content=req.content,
        exploration_context=req.exploration_context,
    )

    return web.json_response(result, status=202)


async def submit_choice(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/choice
    Submit a user choice. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = SubmitChoiceRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.handle_choice(
        session_id=session_id,
        query_id=req.query_id,
        choice=req.choice,
    )

    return web.json_response(result, status=202)


async def submit_direction_choice(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/direction-choice
    Submit a topic direction choice. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = SubmitDirectionChoiceRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.handle_direction_choice(
        session_id=session_id,
        query_id=req.query_id,
        directions=[
            {"id": d.id, "name": d.name} for d in req.directions
        ],
    )

    return web.json_response(result, status=202)


async def navigate(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}/navigate
    Navigate within the topic tree. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    try:
        body = await request.json()
        req = NavigateRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.navigate(
        session_id=session_id,
        exploration_id=exploration_id,
        target_path=req.target_path,
    )

    return web.json_response(result, status=202)


async def mark_explored(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}/mark-explored
    Mark a leaf as explored.
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    try:
        body = await request.json()
        req = MarkExploredRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.mark_explored(
        session_id=session_id,
        exploration_id=exploration_id,
        leaf_id=req.leaf_id,
    )

    return web.json_response(result, status=200)


async def request_analysis(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}/analysis
    Request analysis for a leaf node. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    try:
        body = await request.json()
        req = RequestAnalysisRequest(**body)
    except Exception as e:
        return web.json_response(
            {"error": "invalid_request", "message": str(e)},
            status=400,
        )

    facade = get_facade()
    result = await facade.request_analysis(
        session_id=session_id,
        exploration_id=exploration_id,
        leaf_id=req.leaf_id,
    )

    return web.json_response(result, status=202)


async def end_exploration(request: web.Request) -> web.Response:
    """
    POST /api/v1/guided-exploration/sessions/{session_id}/explorations/{exploration_id}/end
    End an exploration. Results streamed via SSE.
    """
    session_id = request.match_info["session_id"]
    exploration_id = request.match_info["exploration_id"]

    try:
        body = await request.json()
        req = EndExplorationRequest(**body)
    except Exception:
        req = EndExplorationRequest()

    facade = get_facade()
    result = await facade.end_exploration(
        session_id=session_id,
        exploration_id=exploration_id,
        generate_summary=req.generate_summary,
    )

    return web.json_response(result, status=202)


def setup_guided_exploration_routes(app: web.Application) -> None:
    """
    Register guided exploration routes with the application.

    CORS is configured separately in aiohttp_app.py after routes are registered.

    Args:
        app: The aiohttp application
    """
    # Define routes
    routes = [
        ("POST", f"{ROUTE_PREFIX}/sessions", create_session),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}", get_session),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}/stream", stream_session),
        (
            "GET",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations",
            list_explorations,
        ),
        (
            "GET",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}",
            get_exploration,
        ),
        (
            "GET",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}/knowledge-base",
            get_knowledge_base,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/message", send_message),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/choice", submit_choice),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/direction-choice", submit_direction_choice),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}/navigate",
            navigate,
        ),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}/mark-explored",
            mark_explored,
        ),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}/analysis",
            request_analysis,
        ),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/explorations/{{exploration_id}}/end",
            end_exploration,
        ),
    ]

    # Register routes
    for method, path, handler in routes:
        resource = app.router.add_resource(path)
        resource.add_route(method, handler)
        logger.info(f"Registered guided exploration route: {method} {path}")
