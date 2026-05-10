"""Participant API routes for exploration study."""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web

from src.exploration_study.api.admin_routes import setup_admin_routes
from src.exploration_study.api.dtos import (
    ConsentRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    DemographicsRequest,
    ErrorResponse,
    FeedbackRequest,
    PartyClaimDto,
    PartyClaimsResponse,
    PartySubtopicDto,
    PartyTopicDto,
    QuestionnaireRequest,
    QuizQuestionForParticipant,
    QuizResultResponse,
    QuizScoreResponse,
    QuizStatusResponse,
    QuizSubmissionRequest,
    SessionStateResponse,
    StartTaskResponse,
    StateTransitionResponse,
)
from src.exploration_study.models.study import (
    STUDY_PARTIES,
    STUDY_SUBTOPICS,
    STUDY_TOPIC_LABELS,
    STUDY_TOPICS,
    Study,
    StudyConfig,
)
from src.exploration_study.models.quiz import (
    QuizAnswer,
    QuizStatus,
    QuizSubmission,
    calculate_quiz_score,
)
from src.exploration_study.models.session import (
    CognitiveLoadData,
    DemographicsData,
    ProlificData,
    get_condition_for_group,
)
from src.exploration_study.models.state import StudyState
from src.exploration_study.services.counterbalancer import get_counterbalancer
from src.exploration_study.services.session_repository import get_session_repository
from src.exploration_study.services.study_repository import get_study_repository

logger = logging.getLogger(__name__)

ROUTE_PREFIX = "/api/v1/exploration-study"
GE_ROUTE_PREFIX = "/api/v1/guided-exploration"

# Self-serve session creation config
DEFAULT_STUDY_ID = os.getenv("EXPLORATION_STUDY_DEFAULT_ID", "").strip()
DEFAULT_STUDY_NAME = "Exploration Study (self-serve)"
DEFAULT_STUDY_CONTEXT_ID = "exploration-study"

# Positions JSON files (source of truth for the source pages).
_POSITIONS_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "study-fake-parties"
    / "positions"
)
_positions_cache: dict[str, list[dict]] = {}


def _load_party_positions(party_id: str) -> list[dict]:
    """Load the raw claims JSON for a single party, cached per process."""
    cached = _positions_cache.get(party_id)
    if cached is not None:
        return cached
    path = _POSITIONS_DIR / f"{party_id}.json"
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    _positions_cache[party_id] = data
    return data

# Memoized id of the study used for self-serve session creation.
_default_study_cache: str | None = None


async def _get_or_create_default_study() -> Study:
    """
    Resolve the study used for self-serve session creation.

    Resolution order:
    1. In-memory cache from a prior call
    2. Env-configured EXPLORATION_STUDY_DEFAULT_ID
    3. First existing study in the repo
    4. Auto-create a new study with default config
    """
    global _default_study_cache
    study_repo = get_study_repository()

    if _default_study_cache:
        cached = await study_repo.get_study(_default_study_cache)
        if cached:
            return cached
        _default_study_cache = None

    if DEFAULT_STUDY_ID:
        from_env = await study_repo.get_study(DEFAULT_STUDY_ID)
        if from_env:
            _default_study_cache = from_env.id
            return from_env

    existing = await study_repo.list_studies()
    if existing:
        _default_study_cache = existing[0].id
        return existing[0]

    study = await study_repo.create_study(
        name=DEFAULT_STUDY_NAME,
        config=StudyConfig(context_id=DEFAULT_STUDY_CONTEXT_ID),
    )
    _default_study_cache = study.id
    logger.warning(
        f"Auto-created default exploration study: {study.id} "
        f"(set EXPLORATION_STUDY_DEFAULT_ID to pin this)"
    )
    return study


async def create_session_self_serve(request: web.Request) -> web.Response:
    """
    POST /api/v1/exploration-study/sessions

    Create a new self-serve study session. The participant is identified
    via Prolific tracking parameters captured in the invitation URL; the
    request must include at least ``prolific_pid`` and
    ``prolific_session_id``. Repeat calls for the same
    ``prolific_session_id`` return the existing session (idempotent).
    """
    try:
        raw = await request.json()
    except Exception:
        return web.json_response(
            ErrorResponse(
                error="Invalid request body",
                detail="Expected JSON body with Prolific identifiers",
            ).model_dump(),
            status=400,
        )

    try:
        req = CreateSessionRequest(**(raw or {}))
    except Exception as e:
        return web.json_response(
            ErrorResponse(error="Invalid request body", detail=str(e)).model_dump(),
            status=400,
        )

    if not req.prolific_pid or not req.prolific_session_id:
        return web.json_response(
            ErrorResponse(
                error="Missing Prolific identifiers",
                detail="prolific_pid and prolific_session_id are required",
            ).model_dump(),
            status=400,
        )

    session_repo = get_session_repository()

    # Legacy fallback: older sessions were keyed by uuid with prolific.session_id
    # stored as a queryable field. Newer sessions are gated by an atomic claim
    # (see ``claim_or_create_self_serve_session``), so once a participant has
    # been migrated they'll match the claim path; the field-query is only for
    # pre-existing data created before this fix.
    existing = await session_repo.get_session_by_prolific_session_id(
        req.prolific_session_id
    )
    if existing is not None:
        logger.info(
            f"Reusing existing session {existing.id} for "
            f"prolific_session_id={req.prolific_session_id}"
        )
        return web.json_response(
            CreateSessionResponse(
                session_id=existing.id,
                state=existing.state,
            ).model_dump(mode="json"),
            status=200,
        )

    prolific = ProlificData(
        pid=req.prolific_pid,
        study_id=req.prolific_study_id,
        session_id=req.prolific_session_id,
    )

    study = await _get_or_create_default_study()

    counterbalancer = get_counterbalancer()
    group = await counterbalancer.assign_group(study.id)
    condition = get_condition_for_group(group, study.config.topics)

    session, was_created = await session_repo.claim_or_create_self_serve_session(
        prolific_session_id=req.prolific_session_id,
        study_id=study.id,
        group=group,
        condition=condition,
        prolific=prolific,
    )

    if not was_created:
        logger.info(
            f"Lost claim race for prolific_session_id="
            f"{req.prolific_session_id}; returning existing "
            f"session {session.id}"
        )

    response = CreateSessionResponse(
        session_id=session.id,
        state=session.state,
    )
    return web.json_response(
        response.model_dump(mode="json"),
        status=201 if was_created else 200,
    )


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
    await session_repo.update_state(session_id, StudyState.TUTORIAL)
    await session_repo.mark_started(session_id)

    response = StateTransitionResponse(
        previous_state=StudyState.CONSENT,
        current_state=StudyState.TUTORIAL,
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
        ai_chat_usage_frequency=req.ai_chat_usage_frequency,
    )

    await session_repo.update_participant_data(session_id, participant_data)
    # Demographics is the last survey step; close out the session.
    await session_repo.mark_completed(session_id)

    response = StateTransitionResponse(
        previous_state=StudyState.DEMOGRAPHICS,
        current_state=StudyState.COMPLETE,
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

    # Create a guided exploration session via the facade.
    # Study sessions always use the fake-manifesto in-memory RAG, keyed by
    # topic via a synthetic context_id of the form ``study-<topic>``. The
    # topic comes from the participant's assigned condition.
    from src.exploration_study.facade import get_facade

    facade = get_facade()

    study_context_id = f"study-{condition.topic}"

    ge_session = await facade.create_exploration_session(
        context_id=study_context_id,
        mode=condition.system.value,
        max_claims_per_party=condition.max_claims_per_party,
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

    # Sample quiz from the hand-authored corpus, gated by encountered positions.
    from src.exploration_study.facade import get_facade

    facade = get_facade()
    try:
        await facade.start_quiz_generation(session_id=session_id)
    except ValueError as e:
        return web.json_response(
            ErrorResponse(
                error="Quiz generation failed",
                detail=str(e),
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
    Submit Cognitive Load (Klepsch et al., 2017) and UEQ-S.
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
    condition.cognitive_load = CognitiveLoadData(
        cl_icl_1=req.cognitive_load.cl_icl_1,
        cl_icl_2=req.cognitive_load.cl_icl_2,
        cl_ecl_1=req.cognitive_load.cl_ecl_1,
        cl_ecl_2=req.cognitive_load.cl_ecl_2,
        cl_ecl_3=req.cognitive_load.cl_ecl_3,
        cl_gcl_1=req.cognitive_load.cl_gcl_1,
        cl_gcl_2=req.cognitive_load.cl_gcl_2,
    )
    condition.attention_check = req.attention_check
    condition.ueq_s = req.ueq_s
    condition.questionnaire_submitted_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    await session_repo.update_state(session_id, StudyState.QUIZ)

    response = StateTransitionResponse(
        previous_state=StudyState.QUESTIONNAIRE,
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
        participant_questions = [
            QuizQuestionForParticipant(
                id=q.id,
                question=q.question,
                options=q.options,
            )
            for q in quiz.questions
        ]
        response = QuizStatusResponse(
            status=quiz.status,
            is_ready=True,
            questions=participant_questions,
        )
    else:
        response = QuizStatusResponse(
            status=quiz.status,
            is_ready=False,
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

    from src.exploration_study.models.quiz import grade_answer

    answers = []
    for answer_req in req.answers:
        question = next(
            (q for q in quiz.questions if q.id == answer_req.question_id), None
        )
        is_correct = grade_answer(question, answer_req.selected_index) if question else False

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

    condition = session.condition
    condition.quiz_id = quiz.id
    condition.quiz_submitted_at = datetime.now(timezone.utc)
    await session_repo.update_condition_data(session_id, condition)

    await session_repo.update_state(session_id, StudyState.DEMOGRAPHICS)

    response = QuizResultResponse(
        total_correct=total_correct,
        total_questions=total_questions,
        score_percentage=score_percentage,
        next_state=StudyState.DEMOGRAPHICS,
    )
    return web.json_response(response.model_dump(mode="json"))


async def get_party_claims(request: web.Request) -> web.Response:
    """
    GET /api/v1/exploration-study/parties/{party_id}/claims

    Return all claims for a party, grouped by topic and subtopic, in the
    display order defined by ``STUDY_SUBTOPICS``. Used by the study source
    pages that citations deep-link into.
    """
    party_id = request.match_info["party_id"].strip().lower()

    party_name = next(
        (p for p in STUDY_PARTIES if p.lower() == party_id),
        None,
    )
    if party_name is None:
        return web.json_response(
            ErrorResponse(
                error="Unknown party",
                detail=f"party_id must be one of {[p.lower() for p in STUDY_PARTIES]}",
            ).model_dump(),
            status=404,
        )

    try:
        positions = _load_party_positions(party_id)
    except FileNotFoundError:
        logger.error(f"Positions file missing for party {party_id}")
        return web.json_response(
            ErrorResponse(error="Party positions not found").model_dump(),
            status=404,
        )

    # Index claims by (topic, subtopic) in source order so claims on the page
    # appear in the same sequence as in the JSON.
    by_topic_subtopic: dict[str, dict[str, list[dict]]] = {
        topic: {slug: [] for slug, _ in STUDY_SUBTOPICS.get(topic, [])}
        for topic in STUDY_TOPICS
    }
    for claim in positions:
        topic = claim.get("topic")
        subtopic = claim.get("subtopic")
        if topic not in by_topic_subtopic:
            continue
        if subtopic not in by_topic_subtopic[topic]:
            # Unexpected subtopic — log but don't drop the claim; place it
            # under a synthetic bucket that will be rendered at the end.
            logger.warning(
                f"Claim {claim.get('id')} has unknown subtopic '{subtopic}' "
                f"for topic '{topic}'"
            )
            by_topic_subtopic[topic].setdefault("_uncategorized", []).append(claim)
            continue
        by_topic_subtopic[topic][subtopic].append(claim)

    topics_out: list[PartyTopicDto] = []
    for topic in STUDY_TOPICS:
        topic_label = STUDY_TOPIC_LABELS.get(topic, topic)
        subtopic_catalog = STUDY_SUBTOPICS.get(topic, [])
        subtopics_out: list[PartySubtopicDto] = []
        seen_slugs: set[str] = set()

        for slug, label in subtopic_catalog:
            claims = by_topic_subtopic[topic].get(slug, [])
            seen_slugs.add(slug)
            if not claims:
                continue
            subtopics_out.append(
                PartySubtopicDto(
                    slug=slug,
                    label=label,
                    claims=[
                        PartyClaimDto(
                            id=c["id"],
                            claim=c["claim"],
                            argument=c["argument"],
                        )
                        for c in claims
                    ],
                )
            )

        # Any stray buckets (e.g. "_uncategorized") rendered last.
        for slug, claims in by_topic_subtopic[topic].items():
            if slug in seen_slugs or not claims:
                continue
            subtopics_out.append(
                PartySubtopicDto(
                    slug=slug,
                    label="Weitere",
                    claims=[
                        PartyClaimDto(
                            id=c["id"],
                            claim=c["claim"],
                            argument=c["argument"],
                        )
                        for c in claims
                    ],
                )
            )

        if subtopics_out:
            topics_out.append(
                PartyTopicDto(
                    slug=topic,
                    label=topic_label,
                    subtopics=subtopics_out,
                )
            )

    response = PartyClaimsResponse(
        party_id=party_id,
        party_name=party_name,
        topics=topics_out,
    )
    return web.json_response(response.model_dump(mode="json"))


async def get_quiz_result(request: web.Request) -> web.Response:
    """
    GET /api/v1/exploration-study/sessions/{session_id}/quiz-result

    Return the participant's persisted quiz score so it can be displayed
    on the feedback page after the quiz has been submitted.
    """
    session_id = request.match_info["session_id"]

    session_repo = get_session_repository()
    session = await session_repo.get_session(session_id)
    if not session:
        return web.json_response(
            ErrorResponse(error="Session not found").model_dump(),
            status=404,
        )

    submission = await session_repo.get_latest_quiz_submission(session_id)
    if submission is None:
        return web.json_response(
            ErrorResponse(error="No quiz submission found").model_dump(),
            status=404,
        )

    response = QuizScoreResponse(
        total_correct=submission.total_correct,
        total_questions=submission.total_questions,
        score_percentage=submission.score_percentage,
    )
    return web.json_response(response.model_dump(mode="json"))


async def prolific_redirect(request: web.Request) -> web.Response:
    """
    GET /api/v1/exploration-study/sessions/{session_id}/prolific-redirect

    Redirect a completed participant back to the Prolific completion URL
    configured in ``PROLIFIC_STUDY_REDIRECT_URL`` and stamp the first
    redirect time on the session for analysis. Subsequent calls re-redirect
    but do not overwrite the original timestamp.
    """
    session_id = request.match_info["session_id"]

    redirect_url = os.getenv("PROLIFIC_STUDY_REDIRECT_URL", "").strip()
    if not redirect_url:
        return web.json_response(
            ErrorResponse(
                error="Redirect URL not configured",
                detail="PROLIFIC_STUDY_REDIRECT_URL is not set on the backend.",
            ).model_dump(),
            status=500,
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

    if session.prolific_redirected_at is None:
        await session_repo.mark_prolific_redirected(session_id)

    raise web.HTTPSeeOther(location=redirect_url)


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
        ("POST", f"{ROUTE_PREFIX}/sessions", create_session_self_serve),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}", get_session_state),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/consent", submit_consent),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/demographics",
            submit_demographics,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/tutorial", complete_tutorial),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/start", start_task),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/task/end", end_task),
        (
            "POST",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/questionnaire",
            submit_questionnaire,
        ),
        ("GET", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz", get_quiz),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz", submit_quiz),
        (
            "GET",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/quiz-result",
            get_quiz_result,
        ),
        ("POST", f"{ROUTE_PREFIX}/sessions/{{session_id}}/feedback", submit_feedback),
        (
            "GET",
            f"{ROUTE_PREFIX}/sessions/{{session_id}}/prolific-redirect",
            prolific_redirect,
        ),
        ("GET", f"{ROUTE_PREFIX}/parties/{{party_id}}/claims", get_party_claims),
    ]

    for method, path, handler in participant_routes:
        resource = app.router.add_resource(path)
        resource.add_route(method, handler)
        logger.info(f"Registered exploration study route: {method} {path}")

    # Register admin routes
    setup_admin_routes(app)
