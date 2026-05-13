"""Facade for exploration study - public module interface."""

import logging
from datetime import datetime, timezone
from typing import Literal

from src.exploration_study.models.quiz import QuizStatus
from src.exploration_study.services.quiz_sampler import sample_quiz
from src.exploration_study.services.session_repository import (
    SessionRepository,
    get_session_repository,
)

logger = logging.getLogger(__name__)

QUIZ_NUM_QUESTIONS = 10


class ExplorationStudyFacade:
    """
    Public interface for exploration study module.

    Coordinates between study sessions, quiz sampling, and the
    guided exploration module.
    """

    def __init__(
        self,
        session_repository: SessionRepository,
    ) -> None:
        self._session_repo = session_repository

    async def create_exploration_session(
        self,
        context_id: str,
        mode: Literal["guided", "baseline"] = "guided",
        max_claims_per_party: int | None = None,
    ) -> dict:
        """
        Create a guided exploration session for a study task.

        Args:
            context_id: The context ID (e.g., "study-fake-parties")
            mode: "guided" for full exploration, "baseline" for summary-only
            max_claims_per_party: Optional cap on baseline claims surfaced
                per party per turn (study C groups). None = no cap.

        Returns:
            Dict with session_id and stream_url
        """
        # Import here to avoid circular imports
        from src.guided_exploration import get_facade as get_ge_facade
        from src.guided_exploration.models import SessionMode

        ge_facade = get_ge_facade()

        session_mode = SessionMode.GUIDED if mode == "guided" else SessionMode.BASELINE

        session_info = await ge_facade.create_session(
            context_id=context_id,
            user_id=None,  # Study sessions don't have user auth
            mode=session_mode,
            max_claims_per_party=max_claims_per_party,
        )

        logger.info(
            f"Created exploration session {session_info.session_id} "
            f"with mode={mode} max_claims_per_party={max_claims_per_party} "
            f"for context={context_id}"
        )

        return {
            "session_id": session_info.session_id,
            "stream_url": session_info.stream_url,
            "mode": mode,
        }

    async def start_quiz_generation(self, session_id: str) -> None:
        """
        Sample a quiz from the corpus for a completed task and persist it.

        Quizzes are now sampled synchronously from a hand-authored corpus
        (``data/study-fake-parties/quiz_questions.json``). Each question
        is tagged with prerequisite position ids; only questions whose
        prerequisites are all in ``positions_encountered`` are eligible.

        The quiz is written with ``status=READY`` immediately. Frontend
        polling resolves on the first call.
        """
        study_session = await self._session_repo.get_session(session_id)
        if study_session is None or study_session.condition is None:
            raise ValueError(
                f"Cannot sample quiz: no session/condition for {session_id}."
            )

        positions_encountered = study_session.condition.positions_encountered or []

        questions = sample_quiz(
            positions_encountered=positions_encountered,
            session_id=session_id,
            n=QUIZ_NUM_QUESTIONS,
        )

        quiz = await self._session_repo.get_session_quiz(session_id)
        if quiz is None:
            quiz = await self._session_repo.create_quiz(session_id)

        await self._session_repo.update_quiz(
            session_id,
            quiz.id,
            {
                "status": QuizStatus.READY.value,
                "questions": [q.model_dump(mode="json") for q in questions],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        logger.info(
            f"Sampled quiz for session={session_id}: {len(questions)} questions "
            f"(positions_encountered={len(positions_encountered)})"
        )


# Singleton instance
_facade: ExplorationStudyFacade | None = None


def get_facade() -> ExplorationStudyFacade:
    """Get or create the global exploration study facade."""
    global _facade
    if _facade is None:
        session_repository = get_session_repository()
        _facade = ExplorationStudyFacade(session_repository)

        # Register the Information Exposure logger on the guided exploration
        # facade. This crosses the module boundary via callback injection so
        # guided_exploration has no hard dependency on exploration_study.
        from src.exploration_study.services.exposure_logger import (
            log_study_exposure,
        )
        from src.guided_exploration import get_facade as get_ge_facade

        try:
            get_ge_facade().set_study_exposure_logger(log_study_exposure)
        except Exception as e:
            logger.warning(f"Could not register study exposure logger: {e}")
    return _facade
