"""Firebase repository for exploration study sessions."""

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from firebase_admin import firestore_async
from google.cloud.firestore_v1 import DocumentReference, FieldFilter

from src.exploration_study.models.quiz import Quiz, QuizStatus, QuizSubmission
from src.exploration_study.models.session import (
    ConditionData,
    ParticipantData,
    StudySession,
)
from src.exploration_study.models.state import StudyState

logger = logging.getLogger(__name__)

# Collection names
SESSIONS_COLLECTION = "exploration_study_sessions"
QUIZZES_SUBCOLLECTION = "quizzes"


class SessionRepository:
    """Firebase repository for exploration study session persistence."""

    def __init__(self) -> None:
        self._db = firestore_async.client()

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        study_id: str,
        group: Literal["A1", "A2", "B1", "B2"],
        condition: ConditionData,
    ) -> StudySession:
        """Create a new pre-generated session."""
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        session = StudySession(
            id=session_id,
            study_id=study_id,
            state=StudyState.CONSENT,
            group=group,
            condition=condition,
            participant_data=ParticipantData(),
            created_at=now,
            started_at=None,
            completed_at=None,
        )

        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.set(session.model_dump(mode="json"))

        logger.info(f"Created session: {session_id} for study: {study_id}")
        return session

    async def get_session(self, session_id: str) -> StudySession | None:
        """Get a session by ID."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return StudySession(**data)

    async def update_session(
        self,
        session_id: str,
        updates: dict,
    ) -> StudySession | None:
        """Update session fields."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        await doc_ref.update(updates)

        return await self.get_session(session_id)

    async def update_state(
        self,
        session_id: str,
        state: StudyState,
    ) -> StudySession | None:
        """Update session state."""
        return await self.update_session(session_id, {"state": state.value})

    async def update_participant_data(
        self,
        session_id: str,
        participant_data: ParticipantData,
    ) -> StudySession | None:
        """Update participant data."""
        return await self.update_session(
            session_id,
            {"participant_data": participant_data.model_dump(mode="json")},
        )

    async def update_condition_data(
        self,
        session_id: str,
        condition_data: ConditionData,
    ) -> StudySession | None:
        """Update condition data."""
        return await self.update_session(
            session_id,
            {"condition": condition_data.model_dump(mode="json")},
        )

    async def mark_started(self, session_id: str) -> StudySession | None:
        """Mark session as started."""
        return await self.update_session(
            session_id,
            {"started_at": datetime.now(timezone.utc).isoformat()},
        )

    async def mark_completed(self, session_id: str) -> StudySession | None:
        """Mark session as completed."""
        return await self.update_session(
            session_id,
            {
                "state": StudyState.COMPLETE.value,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    async def list_sessions_for_study(
        self,
        study_id: str,
    ) -> list[StudySession]:
        """List all sessions for a study."""
        collection_ref = self._db.collection(SESSIONS_COLLECTION)
        # Simple query without ordering to avoid requiring a composite index
        query = collection_ref.where(filter=FieldFilter("study_id", "==", study_id))

        sessions: list[StudySession] = []
        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                sessions.append(StudySession(**data))

        # Sort in Python instead
        sessions.sort(key=lambda s: s.created_at, reverse=True)
        return sessions

    async def count_sessions_by_group(
        self,
        study_id: str,
    ) -> dict[Literal["A1", "A2", "B1", "B2"], int]:
        """Count sessions per group for counterbalancing."""
        # Use a simple query without ordering to avoid requiring a composite index
        collection_ref = self._db.collection(SESSIONS_COLLECTION)
        query = collection_ref.where(filter=FieldFilter("study_id", "==", study_id))

        counts: dict[Literal["A1", "A2", "B1", "B2"], int] = {
            "A1": 0,
            "A2": 0,
            "B1": 0,
            "B2": 0,
        }
        async for doc in query.stream():
            data = doc.to_dict()
            if data and data.get("group") in counts:
                counts[data["group"]] += 1
        return counts

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if deleted, False if not found."""
        doc_ref = self._db.collection(SESSIONS_COLLECTION).document(session_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False

        await doc_ref.delete()
        logger.info(f"Deleted session: {session_id}")
        return True

    # =========================================================================
    # Quiz Operations
    # =========================================================================

    def _get_quiz_ref(self, session_id: str, quiz_id: str) -> DocumentReference:
        """Get reference to a quiz document."""
        return (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection(QUIZZES_SUBCOLLECTION)
            .document(quiz_id)
        )

    async def create_quiz(
        self,
        session_id: str,
    ) -> Quiz:
        """Create a pending quiz for the session."""
        quiz_id = str(uuid4())
        now = datetime.now(timezone.utc)

        quiz = Quiz(
            id=quiz_id,
            session_id=session_id,
            status=QuizStatus.PENDING,
            questions=[],
            created_at=now,
            generated_at=None,
            error_message=None,
        )

        doc_ref = self._get_quiz_ref(session_id, quiz_id)
        await doc_ref.set(quiz.model_dump(mode="json"))

        logger.info(f"Created quiz: {quiz_id} for session: {session_id}")
        return quiz

    async def get_quiz(self, session_id: str, quiz_id: str) -> Quiz | None:
        """Get a quiz by ID."""
        doc_ref = self._get_quiz_ref(session_id, quiz_id)
        doc = await doc_ref.get()  # type: ignore[misc]

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Quiz(**data)

    async def get_session_quiz(
        self,
        session_id: str,
    ) -> Quiz | None:
        """Get the quiz for the session."""
        collection_ref = (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection(QUIZZES_SUBCOLLECTION)
        )
        query = collection_ref.limit(1)

        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                return Quiz(**data)

        return None

    async def update_quiz(
        self,
        session_id: str,
        quiz_id: str,
        updates: dict,
    ) -> Quiz | None:
        """Update quiz fields."""
        doc_ref = self._get_quiz_ref(session_id, quiz_id)
        await doc_ref.update(updates)

        return await self.get_quiz(session_id, quiz_id)

    async def save_quiz_submission(
        self,
        session_id: str,
        submission: QuizSubmission,
    ) -> None:
        """Save a quiz submission."""
        # Store in a submissions subcollection
        doc_ref = (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection("quiz_submissions")
            .document(submission.quiz_id)
        )
        await doc_ref.set(submission.model_dump(mode="json"))


# Singleton instance
_repository: SessionRepository | None = None


def get_session_repository() -> SessionRepository:
    """Get or create the global session repository."""
    global _repository
    if _repository is None:
        _repository = SessionRepository()
    return _repository
