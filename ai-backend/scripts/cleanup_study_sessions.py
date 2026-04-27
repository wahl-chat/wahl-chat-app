#!/usr/bin/env python3
"""
Delete study sessions for a given study that were created before a cutoff.

Defaults are scoped to the in-progress cleanup:
    study_id = 3b97b645-d77e-4e18-b934-0d55733052cf
    cutoff   = 2026-04-27T11:00:00+00:00

Dry-run by default — pass ``--apply`` to actually delete.

Usage:
    # Preview what would be deleted (default)
    uv run python scripts/cleanup_study_sessions.py

    # Actually delete
    uv run python scripts/cleanup_study_sessions.py --apply

    # Override defaults
    uv run python scripts/cleanup_study_sessions.py \
        --study-id <uuid> --before 2026-04-27T11:00:00+00:00 --apply
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION,
    get_session_repository,
)

DEFAULT_STUDY_ID = "3b97b645-d77e-4e18-b934-0d55733052cf"
DEFAULT_CUTOFF = "2026-04-27T11:00:00+00:00"
SESSION_SUBCOLLECTIONS = ("quizzes", "quiz_submissions")


async def _delete_subcollection(session_id: str, name: str) -> int:
    """Delete every document in one subcollection of a session."""
    from firebase_admin import firestore_async

    fs = firestore_async.client()
    coll = (
        fs.collection(SESSIONS_COLLECTION)
        .document(session_id)
        .collection(name)
    )
    deleted = 0
    async for doc in coll.stream():
        await doc.reference.delete()
        deleted += 1
    return deleted


async def cleanup(study_id: str, cutoff: datetime, apply: bool) -> None:
    session_repo = get_session_repository()
    sessions = await session_repo.list_sessions_for_study(study_id)

    targets = [s for s in sessions if s.created_at < cutoff]
    print(f"Study:  {study_id}")
    print(f"Cutoff: {cutoff.isoformat()}")
    print(f"Total sessions for study: {len(sessions)}")
    print(f"Sessions created before cutoff: {len(targets)}")
    if not targets:
        print("Nothing to delete.")
        return

    for s in targets:
        print(
            f"  - {s.id}  state={s.state}  group={s.group}  "
            f"created_at={s.created_at.isoformat()}"
        )

    if not apply:
        print("\n(dry run — pass --apply to actually delete)")
        return

    from firebase_admin import firestore_async

    fs = firestore_async.client()
    deleted_sessions = 0
    deleted_subdocs = 0
    for s in targets:
        for sub in SESSION_SUBCOLLECTIONS:
            deleted_subdocs += await _delete_subcollection(s.id, sub)
        await fs.collection(SESSIONS_COLLECTION).document(s.id).delete()
        deleted_sessions += 1

    print(
        f"\nDeleted {deleted_sessions} sessions and {deleted_subdocs} "
        f"subcollection documents."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-id", default=DEFAULT_STUDY_ID)
    parser.add_argument(
        "--before",
        default=DEFAULT_CUTOFF,
        help="ISO 8601 timestamp; sessions created before this are deleted.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete.")
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.before)
    asyncio.run(cleanup(args.study_id, cutoff, args.apply))


if __name__ == "__main__":
    main()
