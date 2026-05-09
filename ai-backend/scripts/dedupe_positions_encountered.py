#!/usr/bin/env python3
"""
Dedupe ``condition.positions_encountered`` for stored study sessions.

Order-preserving dedupe (first occurrence wins). Dry-run by default —
pass ``--apply`` to actually write.

Usage:
    # Preview across all studies (default)
    uv run python scripts/dedupe_positions_encountered.py

    # Restrict to one study
    uv run python scripts/dedupe_positions_encountered.py --study-id <uuid>

    # Actually write
    uv run python scripts/dedupe_positions_encountered.py --apply
"""

import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION,
    get_session_repository,
)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


async def _all_sessions():
    from firebase_admin import firestore_async

    fs = firestore_async.client()
    async for doc in fs.collection(SESSIONS_COLLECTION).stream():
        data = doc.to_dict() or {}
        yield doc.id, data


async def cleanup(study_id: str | None, apply: bool) -> None:
    if study_id:
        repo = get_session_repository()
        sessions = await repo.list_sessions_for_study(study_id)
        rows = [
            (s.id, list(s.condition.positions_encountered or []))
            for s in sessions
        ]
    else:
        rows = []
        async for sid, data in _all_sessions():
            cond = (data or {}).get("condition") or {}
            rows.append((sid, list(cond.get("positions_encountered") or [])))

    targets: list[tuple[str, list[str], list[str]]] = []
    for sid, original in rows:
        deduped = _dedupe(original)
        if len(deduped) != len(original):
            targets.append((sid, original, deduped))

    print(f"Scanned sessions:           {len(rows)}")
    print(f"Sessions with duplicates:   {len(targets)}")
    if not targets:
        print("Nothing to fix.")
        return

    total_removed = 0
    for sid, original, deduped in targets:
        removed = len(original) - len(deduped)
        total_removed += removed
        print(
            f"  - {sid}  before={len(original)}  after={len(deduped)}  "
            f"removed={removed}"
        )
    print(f"Total duplicate entries to remove: {total_removed}")

    if not apply:
        print("\n(dry run — pass --apply to actually write)")
        return

    from firebase_admin import firestore_async

    fs = firestore_async.client()
    written = 0
    for sid, _original, deduped in targets:
        await fs.collection(SESSIONS_COLLECTION).document(sid).update(
            {"condition.positions_encountered": deduped}
        )
        written += 1
    print(f"\nUpdated {written} sessions.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--study-id",
        default=None,
        help="Restrict to one study; default scans all sessions.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually write.")
    args = parser.parse_args()

    asyncio.run(cleanup(args.study_id, args.apply))


if __name__ == "__main__":
    main()
