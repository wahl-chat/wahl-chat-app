"""Admin API routes for exploration study management."""

import logging
import os
from typing import Literal

from aiohttp import web

from src.exploration_study.api.dtos import (
    CreateSessionsRequest,
    CreateSessionsResponse,
    CreateStudyRequest,
    CreateStudyResponse,
    ErrorResponse,
    ListSessionsResponse,
    SessionSummary,
    StudyResponse,
    UpdateStudyRequest,
)
from src.exploration_study.models.session import get_condition_for_group
from src.exploration_study.models.study import StudyConfig
from src.exploration_study.services.counterbalancer import get_counterbalancer
from src.exploration_study.services.session_repository import get_session_repository
from src.exploration_study.services.study_repository import get_study_repository

logger = logging.getLogger(__name__)

ADMIN_KEY = os.getenv("STUDY_ADMIN_KEY", "")
ADMIN_ROUTE_PREFIX = "/api/v1/exploration-study/admin"


def require_admin(request: web.Request) -> None:
    """Check admin authentication. Raises HTTPUnauthorized if invalid."""
    if not ADMIN_KEY:
        raise web.HTTPServiceUnavailable(
            text="Admin API not configured (STUDY_ADMIN_KEY not set)"
        )

    provided_key = request.headers.get("X-Admin-Key", "")
    if not provided_key or provided_key != ADMIN_KEY:
        raise web.HTTPUnauthorized(text="Invalid or missing admin key")


# =============================================================================
# Study Management
# =============================================================================


async def create_study(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/admin/studies
    Create a new study.
    """
    require_admin(request)

    try:
        body = await request.json()
        req = CreateStudyRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    study_repo = get_study_repository()

    config = StudyConfig(
        context_id=req.context_id,
        topics=req.topics,
        task_duration_seconds=req.task_duration_seconds,
        parties=req.parties,
    )

    study = await study_repo.create_study(name=req.name, config=config)

    response = CreateStudyResponse(
        id=study.id,
        name=study.name,
        status=study.status,
        created_at=study.created_at,
    )
    return web.json_response(response.model_dump(mode="json"), status=201)


async def list_studies(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/admin/studies
    List all studies.
    """
    require_admin(request)

    study_repo = get_study_repository()
    session_repo = get_session_repository()

    studies = await study_repo.list_studies()

    responses = []
    for study in studies:
        sessions = await session_repo.list_sessions_for_study(study.id)
        responses.append(
            StudyResponse(
                id=study.id,
                name=study.name,
                status=study.status,
                context_id=study.config.context_id,
                topics=study.config.topics,
                task_duration_seconds=study.config.task_duration_seconds,
                parties=study.config.parties,
                created_at=study.created_at,
                updated_at=study.updated_at,
                session_count=len(sessions),
            ).model_dump(mode="json")
        )

    return web.json_response(responses)


async def get_study(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/admin/studies/{study_id}
    Get a specific study.
    """
    require_admin(request)

    study_id = request.match_info["study_id"]
    study_repo = get_study_repository()
    session_repo = get_session_repository()

    study = await study_repo.get_study(study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    sessions = await session_repo.list_sessions_for_study(study.id)

    response = StudyResponse(
        id=study.id,
        name=study.name,
        status=study.status,
        context_id=study.config.context_id,
        topics=study.config.topics,
        task_duration_seconds=study.config.task_duration_seconds,
        parties=study.config.parties,
        created_at=study.created_at,
        updated_at=study.updated_at,
        session_count=len(sessions),
    )
    return web.json_response(response.model_dump(mode="json"))


async def update_study(request: web.Request) -> web.Response:
    """
    PATCH /api/exploration-study/admin/studies/{study_id}
    Update a study.
    """
    require_admin(request)

    study_id = request.match_info["study_id"]

    try:
        body = await request.json()
        req = UpdateStudyRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    study_repo = get_study_repository()

    study = await study_repo.get_study(study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.status is not None:
        updates["status"] = req.status.value

    if updates:
        updated_study = await study_repo.update_study(study_id, updates)
        if updated_study:
            study = updated_study

    session_repo = get_session_repository()
    sessions = await session_repo.list_sessions_for_study(study_id)

    response = StudyResponse(
        id=study.id,
        name=study.name,
        status=study.status,
        context_id=study.config.context_id,
        topics=study.config.topics,
        task_duration_seconds=study.config.task_duration_seconds,
        parties=study.config.parties,
        created_at=study.created_at,
        updated_at=study.updated_at,
        session_count=len(sessions),
    )
    return web.json_response(response.model_dump(mode="json"))


# =============================================================================
# Session Management
# =============================================================================


async def create_sessions(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/admin/studies/{study_id}/sessions
    Create multiple participant sessions.
    """
    require_admin(request)

    study_id = request.match_info["study_id"]

    try:
        body = await request.json()
        req = CreateSessionsRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    study_repo = get_study_repository()
    study = await study_repo.get_study(study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    session_repo = get_session_repository()
    counterbalancer = get_counterbalancer()

    session_ids = []
    for _ in range(req.count):
        # Assign group for counterbalancing
        group = await counterbalancer.assign_group(study_id)

        # Create condition data based on group
        condition = get_condition_for_group(group, study.config.topics)

        # Create the session
        session = await session_repo.create_session(
            study_id=study_id,
            group=group,
            condition=condition,
        )
        session_ids.append(session.id)

    # Get final counts
    group_counts = await counterbalancer.get_group_counts(study_id)

    response = CreateSessionsResponse(
        session_ids=session_ids,
        group_counts=group_counts,
    )
    return web.json_response(response.model_dump(mode="json"), status=201)


async def list_sessions(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/admin/studies/{study_id}/sessions
    List all sessions for a study.
    """
    require_admin(request)

    study_id = request.match_info["study_id"]

    study_repo = get_study_repository()
    study = await study_repo.get_study(study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    session_repo = get_session_repository()
    sessions = await session_repo.list_sessions_for_study(study_id)

    # Aggregate stats
    by_state: dict[str, int] = {}
    by_group: dict[Literal["A1", "A2", "B1", "B2", "C1", "C2"], int] = {
        "A1": 0,
        "A2": 0,
        "B1": 0,
        "B2": 0,
        "C1": 0,
        "C2": 0,
    }

    summaries = []
    for session in sessions:
        summaries.append(
            SessionSummary(
                id=session.id,
                state=session.state,
                group=session.group,
                created_at=session.created_at,
                started_at=session.started_at,
                completed_at=session.completed_at,
            ).model_dump(mode="json")
        )

        state_key = (
            session.state.value
            if hasattr(session.state, "value")
            else str(session.state)
        )
        by_state[state_key] = by_state.get(state_key, 0) + 1
        if session.group in by_group:
            by_group[session.group] += 1

    response = ListSessionsResponse(
        sessions=summaries,
        total=len(sessions),
        by_state=by_state,
        by_group=by_group,
    )
    return web.json_response(response.model_dump(mode="json"))


async def export_study_data(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/admin/studies/{study_id}/export
    Export study data.
    """
    require_admin(request)

    study_id = request.match_info["study_id"]
    format_type = request.query.get("format", "json")

    study_repo = get_study_repository()
    study = await study_repo.get_study(study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    session_repo = get_session_repository()
    sessions = await session_repo.list_sessions_for_study(study_id)

    if format_type == "json":
        export_data = {
            "study": study.model_dump(mode="json"),
            "sessions": [s.model_dump(mode="json") for s in sessions],
        }
        return web.json_response(export_data)
    elif format_type == "csv":
        # Simple CSV export of session data
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(
            [
                "session_id",
                "group",
                "state",
                "created_at",
                "started_at",
                "completed_at",
                "condition_system",
                "condition_topic",
            ]
        )

        for session in sessions:
            cond = session.condition
            writer.writerow(
                [
                    session.id,
                    session.group,
                    session.state.value
                    if hasattr(session.state, "value")
                    else str(session.state),
                    session.created_at.isoformat() if session.created_at else "",
                    session.started_at.isoformat() if session.started_at else "",
                    session.completed_at.isoformat() if session.completed_at else "",
                    cond.system.value if hasattr(cond.system, "value") else str(cond.system),
                    cond.topic,
                ]
            )

        csv_content = output.getvalue()
        return web.Response(
            text=csv_content,
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="study_{study_id}_export.csv"'
            },
        )
    else:
        return web.json_response(
            ErrorResponse(
                error="Invalid format", detail="Use 'json' or 'csv'"
            ).model_dump(),
            status=400,
        )


def setup_admin_routes(app: web.Application) -> None:
    """Register admin routes with the application."""
    routes = [
        ("POST", f"{ADMIN_ROUTE_PREFIX}/studies", create_study),
        ("GET", f"{ADMIN_ROUTE_PREFIX}/studies", list_studies),
        ("GET", f"{ADMIN_ROUTE_PREFIX}/studies/{{study_id}}", get_study),
        ("PATCH", f"{ADMIN_ROUTE_PREFIX}/studies/{{study_id}}", update_study),
        (
            "POST",
            f"{ADMIN_ROUTE_PREFIX}/studies/{{study_id}}/sessions",
            create_sessions,
        ),
        ("GET", f"{ADMIN_ROUTE_PREFIX}/studies/{{study_id}}/sessions", list_sessions),
        ("GET", f"{ADMIN_ROUTE_PREFIX}/studies/{{study_id}}/export", export_study_data),
    ]

    for method, path, handler in routes:
        resource = app.router.add_resource(path)
        resource.add_route(method, handler)
        logger.info(f"Registered admin route: {method} {path}")
