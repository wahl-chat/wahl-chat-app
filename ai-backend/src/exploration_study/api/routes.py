"""Participant API routes for exploration study."""

import logging
from datetime import datetime, timezone

from aiohttp import web

from src.exploration_study.api.admin_routes import setup_admin_routes
from src.exploration_study.api.dtos import (
    ConsentRequest,
    DemographicsRequest,
    ErrorResponse,
    FeedbackRequest,
    LiteracyRequest,
    QuestionnaireRequest,
    QuizResultResponse,
    QuizStatusResponse,
    QuizSubmissionRequest,
    RecallRequest,
    SessionStateResponse,
    StartTaskResponse,
    StateTransitionResponse,
)
from src.exploration_study.models.quiz import (
    QuizAnswer,
    QuizStatus,
    QuizSubmission,
    calculate_quiz_score,
)
from src.exploration_study.models.session import (
    DemographicsData,
    LiteracyData,
    ManipulationChecks,
)
from src.exploration_study.models.state import StudyState
from src.exploration_study.services.session_repository import get_session_repository
from src.exploration_study.services.study_repository import get_study_repository

logger = logging.getLogger(__name__)

ROUTE_PREFIX = "/api/v1/exploration-study"
GE_ROUTE_PREFIX = "/api/v1/guided-exploration"


async def get_session_state(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/sessions/{session_id}
    Get current session state and data for participant.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    study_repo = get_study_repository()
    study = await study_repo.get_study(session.study_id)

    condition = session.condition

    response = SessionStateResponse(
        session_id=session.id,
        state=session.state,
        group=session.group,
        current_condition=condition.system,
        current_system=condition.system,
        current_topic=condition.topic,
        chat_id=condition.chat_id,
        task_duration_seconds=study.config.task_duration_seconds if study else 600,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_consent(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/consent
    Submit consent.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = ConsentRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.CONSENT:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.CONSENT}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    if not req.consent_given:
        return web.json_response(
            ErrorResponse(error="Consent required to participate").model_dump(),
            status=400,
        )

    participant_data = session.participant_data
    participant_data.consent_given = True
    participant_data.consent_timestamp = datetime.now(timezone.utc)

    await session_repo.update_participant_data(session_id, participant_data)
    await session_repo.update_state(session_id, StudyState.DEMOGRAPHICS)
    await session_repo.mark_started(session_id)

    response = StateTransitionResponse(
        previous_state=StudyState.CONSENT,
        current_state=StudyState.DEMOGRAPHICS,
        message="Consent recorded",
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_demographics(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/demographics
    Submit demographics.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = DemographicsRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.DEMOGRAPHICS:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.DEMOGRAPHICS}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    participant_data = session.participant_data
    participant_data.demographics = DemographicsData(
        age_range=req.age_range,
        gender=req.gender,
        education=req.education,
        political_interest=req.political_interest,
    )

    await session_repo.update_participant_data(session_id, participant_data)
    await session_repo.update_state(session_id, StudyState.LITERACY)

    response = StateTransitionResponse(
        previous_state=StudyState.DEMOGRAPHICS,
        current_state=StudyState.LITERACY,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_literacy(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/literacy
    Submit literacy screening.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = LiteracyRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.LITERACY:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.LITERACY}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    correct_answers = {
        "lit_1": "2",
        "lit_2": "Bundestag",
        "lit_3": "4 Jahre",
    }

    score = 0
    for q_id, correct in correct_answers.items():
        if req.political_literacy_answers.get(q_id) == correct:
            score += 1

    participant_data = session.participant_data
    participant_data.literacy = LiteracyData(
        ai_familiarity=req.ai_familiarity,
        chatbot_usage=req.chatbot_usage,
        news_consumption=req.news_consumption,
        political_literacy_answers=req.political_literacy_answers,
        political_literacy_score=score,
    )

    await session_repo.update_participant_data(session_id, participant_data)
    await session_repo.update_state(session_id, StudyState.TUTORIAL)

    response = StateTransitionResponse(
        previous_state=StudyState.LITERACY,
        current_state=StudyState.TUTORIAL,
    )
    return web.json_response(response.model_dump(mode="json"))


async def complete_tutorial(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/tutorial
    Mark tutorial as complete.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.TUTORIAL:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.TUTORIAL}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    await session_repo.update_state(session_id, StudyState.TASK)

    response = StateTransitionResponse(
        previous_state=StudyState.TUTORIAL,
        current_state=StudyState.TASK,
    )
    return web.json_response(response.model_dump(mode="json"))


async def start_task(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/task/start
    Start the task.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.TASK:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.TASK}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    study_repo = get_study_repository()
    study = await study_repo.get_study(session.study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    condition = session.condition

    # Create a guided exploration session via the facade
    from src.exploration_study.facade import get_facade

    facade = get_facade()

    ge_session = await facade.create_exploration_session(
        context_id=study.config.context_id,
        mode=condition.system.value,
    )

    # Update condition with chat ID and start time
    condition.chat_id = ge_session["session_id"]
    condition.started_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    response = StartTaskResponse(
        system=condition.system,
        topic=condition.topic,
        chat_id=ge_session["session_id"],
        stream_url=f"{GE_ROUTE_PREFIX}/sessions/{ge_session['session_id']}/stream",
        duration_seconds=study.config.task_duration_seconds,
        next_state=StudyState.QUESTIONNAIRE,
    )
    return web.json_response(response.model_dump(mode="json"))


async def end_task(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/task/end
    End the task and trigger quiz generation.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.TASK:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {StudyState.TASK}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    condition = session.condition
    condition.ended_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    # Get study for quiz generation
    study_repo = get_study_repository()
    study = await study_repo.get_study(session.study_id)

    # Start quiz generation in background
    if study and condition.chat_id:
        from src.exploration_study.facade import get_facade

        facade = get_facade()
        try:
            await facade.start_quiz_generation(
                session_id=session_id,
                topic=condition.topic,
                parties=study.config.parties,
                chat_id=condition.chat_id,
            )
        except ValueError as e:
            return web.json_response(
                ErrorResponse(
                    error="Quiz generation failed",
                    detail=str(e),
                ).model_dump(),
                status=400,
            )
    else:
        return web.json_response(
            ErrorResponse(
                error="Cannot generate quiz",
                detail="Missing study or chat_id",
            ).model_dump(),
            status=400,
        )

    await session_repo.update_state(session_id, StudyState.QUESTIONNAIRE)

    response = StateTransitionResponse(
        previous_state=StudyState.TASK,
        current_state=StudyState.QUESTIONNAIRE,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_questionnaire(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/questionnaire
    Submit NASA-TLX and UEQ-S questionnaire.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = QuestionnaireRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.QUESTIONNAIRE:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {StudyState.QUESTIONNAIRE}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    condition = session.condition
    condition.nasa_tlx = req.nasa_tlx
    condition.ueq_s = req.ueq_s
    condition.manipulation_checks = ManipulationChecks(
        depth=req.manipulation_checks.depth,
        clarity=req.manipulation_checks.clarity,
        task_clarity=req.manipulation_checks.task_clarity,
        technical=req.manipulation_checks.technical,
    )
    condition.questionnaire_submitted_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    await session_repo.update_state(session_id, StudyState.RECALL)

    response = StateTransitionResponse(
        previous_state=StudyState.QUESTIONNAIRE,
        current_state=StudyState.RECALL,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_recall(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/recall
    Submit free recall.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = RecallRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.RECALL:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {StudyState.RECALL}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    condition = session.condition
    condition.recall_text = req.text
    condition.recall_submitted_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    await session_repo.update_state(session_id, StudyState.QUIZ)

    response = StateTransitionResponse(
        previous_state=StudyState.RECALL,
        current_state=StudyState.QUIZ,
    )
    return web.json_response(response.model_dump(mode="json"))


async def get_quiz(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/sessions/{session_id}/quiz
    Get quiz status and questions if ready.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    quiz = await session_repo.get_session_quiz(session_id)

    if not quiz:
        response = QuizStatusResponse(
            status=QuizStatus.PENDING,
            is_ready=False,
        )
        return web.json_response(response.model_dump(mode="json"))

    is_ready = quiz.status == QuizStatus.READY

    if is_ready:
        response = QuizStatusResponse(
            status=quiz.status,
            is_ready=True,
            questions=quiz.questions,
        )
    else:
        response = QuizStatusResponse(
            status=quiz.status,
            is_ready=False,
            error_message=quiz.error_message,
        )

    return web.json_response(response.model_dump(mode="json"))


async def submit_quiz(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/quiz
    Submit quiz answers and complete the study.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = QuizSubmissionRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.QUIZ:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {StudyState.QUIZ}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    quiz = await session_repo.get_session_quiz(session_id)
    if not quiz or quiz.status != QuizStatus.READY:
        return web.json_response(
            ErrorResponse(error="Quiz not ready").model_dump(),
            status=400,
        )

    # Create answer objects and calculate score
    answers = []
    for answer_req in req.answers:
        question = next(
            (q for q in quiz.questions if q.id == answer_req.question_id), None
        )
        is_correct = (
            question.correct_index == answer_req.selected_index if question else False
        )

        answers.append(
            QuizAnswer(
                question_id=answer_req.question_id,
                selected_index=answer_req.selected_index,
                is_correct=is_correct,
                response_time_ms=answer_req.response_time_ms,
            )
        )

    total_correct, total_questions, score_percentage = calculate_quiz_score(
        quiz.questions, answers
    )

    submission = QuizSubmission(
        quiz_id=quiz.id,
        answers=answers,
        submitted_at=datetime.now(timezone.utc),
        total_correct=total_correct,
        total_questions=total_questions,
        score_percentage=score_percentage,
    )
    await session_repo.save_quiz_submission(session_id, submission)

    # Update condition with quiz submission time
    condition = session.condition
    condition.quiz_id = quiz.id
    condition.quiz_submitted_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    # Mark study as complete
    await session_repo.mark_completed(session_id)

    response = QuizResultResponse(
        total_correct=total_correct,
        total_questions=total_questions,
        score_percentage=score_percentage,
        next_state=StudyState.COMPLETE,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_feedback(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/sessions/{session_id}/feedback
    Submit optional feedback.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = FeedbackRequest(**body)
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    if session.state != StudyState.COMPLETE:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {StudyState.COMPLETE}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    participant_data = session.participant_data
    participant_data.feedback = req.feedback
    await session_repo.update_participant_data(session_id, participant_data)

    return web.json_response({"message": "Feedback saved"})


def setup_exploration_study_routes(app: web.Application) -> None:
    """Register all exploration study routes with the application."""
    participant_routes = [
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}", get_session_state),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/consent", submit_consent),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/demographics",
            submit_demographics,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/literacy", submit_literacy),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/tutorial", complete_tutorial),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/start", start_task),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/end", end_task),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/questionnaire",
            submit_questionnaire,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/recall", submit_recall),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz", get_quiz),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz", submit_quiz),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/feedback", submit_feedback),
    ]

    for method, path, handler in participant_routes:
        resource = app.router.add_resource(path)
        resource.add_route(method, handler)
        logger.info(f"Registered exploration study route: {method} {path}")

    # Register admin routes
    setup_admin_routes(app)
