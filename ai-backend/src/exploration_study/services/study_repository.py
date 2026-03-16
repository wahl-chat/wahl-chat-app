"""Firebase repository for exploration studies."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from firebase_admin import firestore_async

from src.exploration_study.models.study import Study, StudyConfig, StudyStatus

logger = logging.getLogger(__name__)

# Collection name
STUDIES_COLLECTION = "exploration_studies"


class StudyRepository:
    """Firebase repository for exploration study persistence."""

    def __init__(self) -> None:
        self._db = firestore_async.client()

    # =========================================================================
    # Study Operations
    # =========================================================================

    async def create_study(
        self,
        name: str,
        config: StudyConfig,
    ) -> Study:
        """Create a new study."""
        study_id = str(uuid4())
        now = datetime.now(timezone.utc)

        study = Study(
            id=study_id,
            name=name,
            status=StudyStatus.DRAFT,
            config=config,
            created_at=now,
            updated_at=now,
        )

        doc_ref = self._db.collection(STUDIES_COLLECTION).document(study_id)
        await doc_ref.set(study.model_dump(mode="json"))

        logger.info(f"Created study: {study_id} - {name}")
        return study

    async def get_study(self, study_id: str) -> Study | None:
        """Get a study by ID."""
        doc_ref = self._db.collection(STUDIES_COLLECTION).document(study_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        if data is None:
            return None

        return Study(**data)

    async def update_study(
        self,
        study_id: str,
        updates: dict,
    ) -> Study | None:
        """Update study fields."""
        doc_ref = self._db.collection(STUDIES_COLLECTION).document(study_id)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await doc_ref.update(updates)

        return await self.get_study(study_id)

    async def update_study_status(
        self,
        study_id: str,
        status: StudyStatus,
    ) -> Study | None:
        """Update study status."""
        return await self.update_study(study_id, {"status": status.value})

    async def list_studies(self) -> list[Study]:
        """List all studies."""
        collection_ref = self._db.collection(STUDIES_COLLECTION)
        studies: list[Study] = []

        async for doc in collection_ref.order_by(
            "created_at", direction=firestore_async.Query.DESCENDING
        ).stream():
            data = doc.to_dict()
            if data:
                studies.append(Study(**data))

        return studies

    async def delete_study(self, study_id: str) -> bool:
        """Delete a study. Returns True if deleted, False if not found."""
        doc_ref = self._db.collection(STUDIES_COLLECTION).document(study_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False

        await doc_ref.delete()
        logger.info(f"Deleted study: {study_id}")
        return True


# Singleton instance
_repository: StudyRepository | None = None


def get_study_repository() -> StudyRepository:
    """Get or create the global study repository."""
    global _repository
    if _repository is None:
        _repository = StudyRepository()
    return _repository
