#!/usr/bin/env python3
"""
Backfill ``condition.positions_encountered`` with citations from leaf
INITIAL_CONTENT messages that landed before the navigation handler started
logging them.

For each study session, we walk every exploration's conversations, take
the first message of each (the persisted INITIAL_CONTENT for that leaf),
parse the inline ``[id]`` markers out of ``party_positions[*].content``
(the only content_generator field that inlines citations — ``summary`` is
citation-free by prompt), intersect with the leaf's citation pool, and
treat that set as "exposed to the participant". Anything in that set that
is not already in ``condition.positions_encountered`` is missing.

Dry-run by default. Pass ``--apply`` to write.

Usage:
    uv run python scripts/backfill_initial_content_exposure.py \\
        --study-id 5d5b2815-a002-4ca1-b535-ef93d93d98d1
    uv run python scripts/backfill_initial_content_exposure.py \\
        --study-id 5d5b2815-a002-4ca1-b535-ef93d93d98d1 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401

from src.exploration_study.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION as STUDY_SESSIONS_COLLECTION,
    get_session_repository,
)
from src.guided_exploration.services.citation_utils import (  # noqa: E402
    extract_used_citations,
)
from src.guided_exploration.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION as GE_SESSIONS_COLLECTION,
    EXPLORATIONS_SUBCOLLECTION,
    CONVERSATIONS_SUBCOLLECTION,
)
from src.guided_exploration.models.content import Citation  # noqa: E402


def _used_ids_from_initial_content(content: dict) -> set[str]:
    """Extract cited ids actually shown to the participant in a leaf intro.

    ``content`` is the persisted SubtopicContent dict on an INITIAL_CONTENT
    message. We only look at ``party_positions[*].content`` because that is
    the single field where the content_generator emits ``[id]`` markers
    (``summary`` is citation-free by prompt; ``suggested_questions`` are
    plain prose). The pool we match against is the message's ``citations``
    list — that is, the leaf's full citation pool baked into the message
    when it was saved.
    """
    party_positions = content.get("party_positions") or []
    if not party_positions:
        return set()
    initial_text = "\n".join(p.get("content") or "" for p in party_positions)
    if not initial_text.strip():
        return set()
    pool_dicts = content.get("citations") or []
    pool: list[Citation] = []
    for c in pool_dicts:
        try:
            pool.append(Citation(**c))
        except Exception:
            continue
    return {c.id for c in extract_used_citations(initial_text, pool)}


async def _collect_exposed_ids_for_chat(
    fs,
    chat_id: str,
) -> set[str]:
    """Walk all explorations + conversations for a GE chat session and
    return the union of cited ids found in every INITIAL_CONTENT message.
    """
    exposed: set[str] = set()
    explorations_ref = (
        fs.collection(GE_SESSIONS_COLLECTION)
        .document(chat_id)
        .collection(EXPLORATIONS_SUBCOLLECTION)
    )
    async for exp_doc in explorations_ref.stream():
        conv_ref = (
            explorations_ref.document(exp_doc.id)
            .collection(CONVERSATIONS_SUBCOLLECTION)
        )
        async for conv_doc in conv_ref.stream():
            data = conv_doc.to_dict() or {}
            messages = data.get("messages") or []
            if not messages:
                continue
            first = messages[0]
            if first.get("type") != "initial_content":
                continue
            content = first.get("content")
            if not isinstance(content, dict):
                continue
            exposed |= _used_ids_from_initial_content(content)
    return exposed


async def backfill(study_id: str, apply: bool) -> None:
    from firebase_admin import firestore_async

    fs = firestore_async.client()
    repo = get_session_repository()
    sessions = await repo.list_sessions_for_study(study_id)
    if not sessions:
        print(f"No sessions found for study {study_id}.")
        return

    print(f"Scanning {len(sessions)} sessions in study {study_id}\n")

    rows: list[tuple[str, list[str], list[str], list[str]]] = []
    # (session_id, current, exposed_only_in_initial, missing)

    for s in sessions:
        chat_id = s.condition.chat_id
        current = list(s.condition.positions_encountered or [])
        if not chat_id:
            rows.append((s.id, current, [], []))
            continue

        exposed = await _collect_exposed_ids_for_chat(fs, chat_id)
        current_set = set(current)
        missing = sorted(exposed - current_set)
        rows.append((s.id, current, sorted(exposed), missing))

    sessions_with_gap = [r for r in rows if r[3]]

    print(f"{'session_id':<38} {'sys':<9} {'topic':<22} "
          f"{'enc':>4} {'init':>5} {'miss':>5}")
    print("-" * 90)
    for s, (sid, current, exposed, missing) in zip(sessions, rows):
        sys_type = (
            s.condition.system.value
            if hasattr(s.condition.system, "value")
            else str(s.condition.system or "?")
        )
        topic = s.condition.topic or "?"
        print(
            f"{sid:<38} {sys_type:<9} {topic:<22} "
            f"{len(current):>4} {len(exposed):>5} {len(missing):>5}"
        )

    print()
    print(f"Sessions with missing initial-content exposure: "
          f"{len(sessions_with_gap)} / {len(rows)}")

    if not sessions_with_gap:
        print("Nothing to backfill.")
        return

    print("\nDetails (missing ids per session):")
    for sid, current, exposed, missing in sessions_with_gap:
        print(f"  {sid}  +{len(missing)} -> {missing}")

    if not apply:
        print("\n(dry run — pass --apply to actually write)")
        return

    written = 0
    for sid, current, _exposed, missing in sessions_with_gap:
        # Append-preserve-order, no dedup of existing list (storage already
        # de-duplicates via append_positions_encountered semantics, but here
        # we write directly so we keep current order then add missing in
        # sorted order — same convention the live logger uses).
        merged = list(current) + [m for m in missing if m not in current]
        await fs.collection(STUDY_SESSIONS_COLLECTION).document(sid).update(
            {"condition.positions_encountered": merged}
        )
        written += 1
    print(f"\nUpdated {written} sessions.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-id", required=True, help="Study ID to scan.")
    parser.add_argument("--apply", action="store_true", help="Actually write.")
    args = parser.parse_args()

    asyncio.run(backfill(args.study_id, args.apply))


if __name__ == "__main__":
    main()
