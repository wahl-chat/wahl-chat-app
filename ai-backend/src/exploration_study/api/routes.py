"""Participant API routes for exploration study."""

import logging
from datetime import datetime, timezone

from aiohttp import web

from src.exploration_study.api.admin_routes import setup_admin_routes
from src.exploration_study.api.dtos import (
    ConsentRequest,
    DemographicsRequest,
    ErrorResponse,
    LiteracyRequest,
    PreferencesRequest,
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
    PreferencesData,
    TaskKey,
)
from src.exploration_study.models.state import StudyState, get_task_number
from src.exploration_study.services.session_repository import get_session_repository
from src.exploration_study.services.study_repository import get_study_repository

logger = logging.getLogger(__name__)

ROUTE_PREFIX = "/api/v1/exploration-study"


def _task_key(n: int | str) -> TaskKey:
    """Convert task number to TaskKey literal type."""
    key = str(n)
    if key not in ("1", "2"):
        raise ValueError(f"Invalid task number: {n}")
    return key  # type: ignore[return-value]


GE_ROUTE_PREFIX = "/api/v1/guided-exploration"


async def get_session_state(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/session/{session_id}
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

    # Determine current condition info
    task_num = get_task_number(session.state)
    current_condition = None
    current_system = None
    current_topic = None

    if task_num:
        cond_key = _task_key(task_num)
        cond = session.conditions.get(cond_key)
        if cond:
            current_condition = cond.system
            current_system = cond.system
            current_topic = cond.topic

    # Build chat_ids dict from all conditions
    chat_ids: dict[str, str | None] = {}
    for cond_key in ("1", "2"):
        cond = session.conditions.get(cond_key)
        chat_ids[cond_key] = cond.chat_id if cond else None

    response = SessionStateResponse(
        session_id=session.id,
        state=session.state,
        group=session.group,
        current_condition=current_condition,
        current_system=current_system,
        current_topic=current_topic,
        chat_ids=chat_ids,
        task_duration_seconds=study.config.task_duration_seconds if study else 600,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_consent(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/consent
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

    # Check we're in the consent step
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

    # Update participant data
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
    POST /api/exploration-study/session/{session_id}/demographics
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

    # Update participant data
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
    POST /api/exploration-study/session/{session_id}/literacy
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

    # Calculate political literacy score
    # Correct answers for the 3 political literacy questions
    correct_answers = {
        "lit_1": "2",  # Wie viele Stimmen bei der Bundestagswahl? -> 2
        "lit_2": "Bundestag",  # Welches Organ wählt den Bundeskanzler? -> Bundestag
        "lit_3": "4 Jahre",  # Wie lange dauert eine Legislaturperiode? -> 4 Jahre
    }

    score = 0
    for q_id, correct in correct_answers.items():
        if req.political_literacy_answers.get(q_id) == correct:
            score += 1

    # Update participant data
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
    POST /api/exploration-study/session/{session_id}/tutorial
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

    await session_repo.update_state(session_id, StudyState.TASK_1)

    response = StateTransitionResponse(
        previous_state=StudyState.TUTORIAL,
        current_state=StudyState.TASK_1,
    )
    return web.json_response(response.model_dump(mode="json"))


async def start_task(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/task/{n}/start
    Start a task.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(
                error="Invalid task number", detail="Must be 1 or 2"
            ).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    # Check we're in the correct task state
    expected_state = StudyState.TASK_1 if task_n == 1 else StudyState.TASK_2

    if session.state != expected_state:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {expected_state}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    # Get study config
    study_repo = get_study_repository()
    study = await study_repo.get_study(session.study_id)
    if not study:
        return web.json_response(
            ErrorResponse(error="Study not found").model_dump(),
            status=404,
        )

    # Get condition data
    cond_key = _task_key(task_n)
    condition = session.conditions.get(cond_key)
    if not condition:
        return web.json_response(
            ErrorResponse(error="Condition not found").model_dump(),
            status=500,
        )

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
    await session_repo.update_condition_data(session_id, cond_key, condition)

    # Determine the next state after this task ends
    next_state_after_task = (
        StudyState.QUESTIONNAIRE_1 if task_n == 1 else StudyState.QUESTIONNAIRE_2
    )

    response = StartTaskResponse(
        condition_num=task_n,
        system=condition.system,
        topic=condition.topic,
        chat_id=ge_session["session_id"],
        stream_url=f"{GE_ROUTE_PREFIX}/sessions/{ge_session['session_id']}/stream",
        duration_seconds=study.config.task_duration_seconds,
        next_state=next_state_after_task,
    )
    return web.json_response(response.model_dump(mode="json"))


async def end_task(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/task/{n}/end
    End a task and trigger quiz generation.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(error="Invalid task number").model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    expected_state = StudyState.TASK_1 if task_n == 1 else StudyState.TASK_2
    target_state = (
        StudyState.QUESTIONNAIRE_1 if task_n == 1 else StudyState.QUESTIONNAIRE_2
    )

    if session.state != expected_state:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected state {expected_state}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    # Update condition end time
    cond_key = _task_key(task_n)
    condition = session.conditions.get(cond_key)
    if condition:
        condition.ended_at = datetime.now(timezone.utc)
        await session_repo.update_condition_data(session_id, cond_key, condition)

    # Get study for quiz generation
    study_repo = get_study_repository()
    study = await study_repo.get_study(session.study_id)

    # Start quiz generation in background
    if study and condition and condition.chat_id:
        from src.exploration_study.facade import get_facade

        facade = get_facade()
        try:
            await facade.start_quiz_generation(
                session_id=session_id,
                condition_num=task_n,
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
                detail="Missing study, condition, or chat_id",
            ).model_dump(),
            status=400,
        )

    # Transition state
    await session_repo.update_state(session_id, target_state)

    response = StateTransitionResponse(
        previous_state=session.state,
        current_state=target_state,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_questionnaire(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/questionnaire/{n}
    Submit NASA-TLX and UEQ-S questionnaire.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(error="Invalid task number").model_dump(),
            status=400,
        )

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

    expected_state = (
        StudyState.QUESTIONNAIRE_1 if task_n == 1 else StudyState.QUESTIONNAIRE_2
    )
    target_state = StudyState.RECALL_1 if task_n == 1 else StudyState.RECALL_2

    if session.state != expected_state:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {expected_state}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    # Update condition data
    cond_key = _task_key(task_n)
    condition = session.conditions.get(cond_key)
    if condition:
        condition.nasa_tlx = req.nasa_tlx
        condition.ueq_s = req.ueq_s
        condition.manipulation_checks = ManipulationChecks(
            depth=req.manipulation_checks.depth,
            clarity=req.manipulation_checks.clarity,
            task_clarity=req.manipulation_checks.task_clarity,
            technical=req.manipulation_checks.technical,
        )
        condition.questionnaire_submitted_at = datetime.now(timezone.utc)
        await session_repo.update_condition_data(session_id, cond_key, condition)

    await session_repo.update_state(session_id, target_state)

    response = StateTransitionResponse(
        previous_state=session.state,
        current_state=target_state,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_recall(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/recall/{n}
    Submit free recall.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(error="Invalid task number").model_dump(),
            status=400,
        )

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

    expected_state = StudyState.RECALL_1 if task_n == 1 else StudyState.RECALL_2
    target_state = StudyState.QUIZ_1 if task_n == 1 else StudyState.QUIZ_2

    if session.state != expected_state:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {expected_state}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    # Update condition data
    cond_key = _task_key(task_n)
    condition = session.conditions.get(cond_key)
    if condition:
        condition.recall_text = req.text
        condition.recall_submitted_at = datetime.now(timezone.utc)
        await session_repo.update_condition_data(session_id, cond_key, condition)

    await session_repo.update_state(session_id, target_state)

    response = StateTransitionResponse(
        previous_state=session.state,
        current_state=target_state,
    )
    return web.json_response(response.model_dump(mode="json"))


async def get_quiz(request: web.Request) -> web.Response:
    """
    GET /api/exploration-study/session/{session_id}/quiz/{n}
    Get quiz status and questions if ready.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(error="Invalid task number").model_dump(),
            status=400,
        )

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)

    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    quiz = await session_repo.get_quiz_for_condition(session_id, task_n)

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
    POST /api/exploration-study/session/{session_id}/quiz/{n}
    Submit quiz answers.
    """
    session_id = request.match_info["session_id"]
    task_n = int(request.match_info["n"])

    if task_n not in (1, 2):
        return web.json_response(
            ErrorResponse(error="Invalid task number").model_dump(),
            status=400,
        )

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

    expected_state = StudyState.QUIZ_1 if task_n == 1 else StudyState.QUIZ_2
    target_state = StudyState.TASK_2 if task_n == 1 else StudyState.PREFERENCES

    if session.state != expected_state:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {expected_state}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    quiz = await session_repo.get_quiz_for_condition(session_id, task_n)
    if not quiz or quiz.status != QuizStatus.READY:
        return web.json_response(
            ErrorResponse(error="Quiz not ready").model_dump(),
            status=400,
        )

    # Create answer objects and calculate score
    answers = []
    for answer_req in req.answers:
        # Find the question to check correctness
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

    # Calculate score
    total_correct, total_questions, score_percentage = calculate_quiz_score(
        quiz.questions, answers
    )

    # Save submission
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
    cond_key = _task_key(task_n)
    condition = session.conditions.get(cond_key)
    if condition:
        condition.quiz_id = quiz.id
        condition.quiz_submitted_at = datetime.now(timezone.utc)
        await session_repo.update_condition_data(session_id, cond_key, condition)

    # Transition state
    await session_repo.update_state(session_id, target_state)

    response = QuizResultResponse(
        total_correct=total_correct,
        total_questions=total_questions,
        score_percentage=score_percentage,
        next_state=target_state,
    )
    return web.json_response(response.model_dump(mode="json"))


async def submit_preferences(request: web.Request) -> web.Response:
    """
    POST /api/exploration-study/session/{session_id}/preferences
    Submit final preferences comparison.
    """
    session_id = request.match_info["session_id"]

    try:
        body = await request.json()
        req = PreferencesRequest(**body)
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

    if session.state != StudyState.PREFERENCES:
        return web.json_response(
            ErrorResponse(
                error="Invalid state",
                detail=f"Expected {StudyState.PREFERENCES}, got {session.state}",
            ).model_dump(),
            status=400,
        )

    # Update participant data
    participant_data = session.participant_data
    participant_data.preferences = PreferencesData(
        preferred_system=req.preferred_system,
        preference_reason=req.preference_reason,
        better_for_overview=req.better_for_overview,
        better_for_details=req.better_for_details,
        additional_feedback=req.additional_feedback,
    )

    await session_repo.update_participant_data(session_id, participant_data)
    await session_repo.mark_completed(session_id)

    response = StateTransitionResponse(
        previous_state=session.state,
        current_state=StudyState.COMPLETE,
        message="Study completed. Thank you for participating!",
    )
    return web.json_response(response.model_dump(mode="json"))


def setup_exploration_study_routes(app: web.Application) -> None:
    """Register all exploration study routes with the application."""
    # Participant routes
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
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/{{n}}/start",
            start_task,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/{{n}}/end", end_task),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/questionnaire/{{n}}",
            submit_questionnaire,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/recall/{{n}}", submit_recall),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz/{{n}}", get_quiz),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz/{{n}}", submit_quiz),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/preferences",
            submit_preferences,
        ),
    ]

    for method, path, handler in participant_routes:
        resource = app.router.add_resource(path)
        resource.add_route(method, handler)
        logger.info(f"Registered exploration study route: {method} {path}")

    # Register admin routes
    setup_admin_routes(app)
