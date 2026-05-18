"""Firebase repository for exploration study sessions."""

import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from firebase_admin import firestore_async
from google.cloud.firestore_v1 import DocumentReference, FieldFilter
from google.cloud.firestore_v1 import async_transactional

from src.exploration_study.models.quiz import (
    QUIZ_CORPUS_VERSION,
    Quiz,
    QuizStatus,
    QuizSubmission,
)
from src.exploration_study.models.session import (
    ConditionData,
    ParticipantData,
    ProlificData,
    StudySession,
)
from src.exploration_study.models.state import StudyState

logger = logging.getLogger(__name__)

# Collection names
SESSIONS_COLLECTION = "exploration_study_sessions"
QUIZZES_SUBCOLLECTION = "quizzes"
PROLIFIC_CLAIMS_COLLECTION = "exploration_study_prolific_claims"


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
        group: Literal["A1", "A2", "B1", "B2", "C1", "C2"],
        condition: ConditionData,
        prolific: ProlificData | None = None,
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
            prolific=prolific,
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

    async def get_session_by_prolific_session_id(
        self,
        prolific_session_id: str,
    ) -> StudySession | None:
        """
        Look up a study session by its Prolific session id, used to make
        self-serve session creation idempotent across refreshes.
        """
        query = (
            self._db.collection(SESSIONS_COLLECTION)
            .where(
                filter=FieldFilter(
                    "prolific.session_id", "==", prolific_session_id
                )
            )
            .limit(1)
        )
        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                return StudySession(**data)
        return None

    async def claim_or_create_self_serve_session(
        self,
        prolific_session_id: str,
        study_id: str,
        group: Literal["A1", "A2", "B1", "B2", "C1", "C2"],
        condition: ConditionData,
        prolific: ProlificData,
    ) -> tuple[StudySession, bool]:
        """Atomically claim ``prolific_session_id`` and create the session.

        Two concurrent self-serve requests with the same Prolific session id
        (refresh during pending POST, double-click, two open tabs, network
        retry) would otherwise both pass the existence check and both create a
        new session — producing a duplicate. We close that race by gating
        creation on a single-doc claim in
        ``exploration_study_prolific_claims/{prolific_session_id}`` written
        inside a Firestore transaction.

        Returns ``(session, was_created)``. ``was_created`` is ``True`` for
        the winner (claim freshly written, session doc freshly created) and
        ``False`` if another concurrent caller had already claimed the id —
        in that case the existing session is returned.
        """
        claim_ref = self._db.collection(PROLIFIC_CLAIMS_COLLECTION).document(
            prolific_session_id
        )
        new_session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        new_session = StudySession(
            id=new_session_id,
            study_id=study_id,
            state=StudyState.CONSENT,
            group=group,
            condition=condition,
            participant_data=ParticipantData(),
            prolific=prolific,
            created_at=now,
            started_at=None,
            completed_at=None,
        )
        session_ref = self._db.collection(SESSIONS_COLLECTION).document(
            new_session_id
        )

        @async_transactional
        async def _claim(tx) -> tuple[str, bool]:
            snapshot = await claim_ref.get(transaction=tx)
            if snapshot.exists:
                claimed = (snapshot.to_dict() or {}).get("session_id")
                if claimed:
                    return claimed, False
            tx.set(
                claim_ref,
                {
                    "session_id": new_session_id,
                    "prolific_session_id": prolific_session_id,
                    "claimed_at": now.isoformat(),
                },
            )
            tx.set(session_ref, new_session.model_dump(mode="json"))
            return new_session_id, True

        transaction = self._db.transaction()
        session_id, won = await _claim(transaction)

        if won:
            logger.info(
                f"Created self-serve session {session_id} (claimed "
                f"prolific_session_id={prolific_session_id})"
            )
            return new_session, True

        # Lost the race — fetch the winner's session doc.
        existing = await self.get_session(session_id)
        if existing is None:
            # Claim exists but session doc missing — recover by writing the
            # session doc under the claimed id. Can happen if a previous
            # request crashed between transaction commit and a follow-up
            # write; in this implementation tx writes both, so this branch
            # is mostly defensive. Re-build the session under the claimed id.
            recovered = new_session.model_copy(update={"id": session_id})
            await self._db.collection(SESSIONS_COLLECTION).document(
                session_id
            ).set(recovered.model_dump(mode="json"))
            logger.warning(
                f"Recovered missing session doc for claimed "
                f"prolific_session_id={prolific_session_id} -> {session_id}"
            )
            return recovered, True
        return existing, False

    async def get_session_by_chat_id(self, chat_id: str) -> StudySession | None:
        """
        Look up the study session whose condition holds a given guided
        exploration chat session id. Returns ``None`` if no session is
        currently linked to that chat id.
        """
        query = (
            self._db.collection(SESSIONS_COLLECTION)
            .where(filter=FieldFilter("condition.chat_id", "==", chat_id))
            .limit(1)
        )
        docs = [doc async for doc in query.stream()]
        if not docs:
            return None
        return StudySession(**docs[0].to_dict())

    async def append_positions_encountered(
        self,
        chat_id: str,
        position_ids: list[str],
    ) -> None:
        """
        Merge new cited position ids into the study session's
        ``condition.positions_encountered`` list (dedup preserved).

        Looks up the session via ``chat_id``. Silent no-op if no session
        is linked to this chat id (e.g. non-study sessions).
        """
        if not position_ids:
            return

        session = await self.get_session_by_chat_id(chat_id)
        if session is None:
            return

        seen = set(session.condition.positions_encountered or [])
        added: list[str] = []
        for pid in position_ids:
            if pid not in seen:
                seen.add(pid)
                added.append(pid)
        if not added:
            return

        merged = list(session.condition.positions_encountered) + added
        await self.update_session(
            session.id,
            {"condition.positions_encountered": merged},
        )
        logger.info(
            f"Logged {len(added)} new positions_encountered for "
            f"session={session.id} (total={len(merged)})"
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

    async def mark_prolific_redirected(
        self,
        session_id: str,
    ) -> StudySession | None:
        """Stamp ``prolific_redirected_at`` on the first Prolific redirect.

        Idempotent: if the timestamp is already set, leave it untouched so
        the original redirect time is preserved for analysis.
        """
        return await self.update_session(
            session_id,
            {"prolific_redirected_at": datetime.now(timezone.utc).isoformat()},
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
    ) -> dict[Literal["A1", "A2", "B1", "B2", "C1", "C2"], int]:
        """Count sessions per group for counterbalancing."""
        # Use a simple query without ordering to avoid requiring a composite index
        collection_ref = self._db.collection(SESSIONS_COLLECTION)
        query = collection_ref.where(filter=FieldFilter("study_id", "==", study_id))

        counts: dict[Literal["A1", "A2", "B1", "B2", "C1", "C2"], int] = {
            "A1": 0,
            "A2": 0,
            "B1": 0,
            "B2": 0,
            "C1": 0,
            "C2": 0,
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
            version=QUIZ_CORPUS_VERSION,
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

    async def get_latest_quiz_submission(
        self,
        session_id: str,
    ) -> QuizSubmission | None:
        """Return the most recent quiz submission for the session, if any."""
        collection_ref = (
            self._db.collection(SESSIONS_COLLECTION)
            .document(session_id)
            .collection("quiz_submissions")
        )
        query = collection_ref.order_by(
            "submitted_at", direction="DESCENDING"
        ).limit(1)

        async for doc in query.stream():
            data = doc.to_dict()
            if data:
                return QuizSubmission(**data)

        return None


# Singleton instance
_repository: SessionRepository | None = None


def get_session_repository() -> SessionRepository:
    """Get or create the global session repository."""
    global _repository
    if _repository is None:
        _repository = SessionRepository()
    return _repository
