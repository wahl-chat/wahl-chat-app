#!/usr/bin/env python3
"""
Inspect a single study session: verify quiz prerequisites against
positions_encountered, and dump the guided exploration conversation so
the two can be eyeballed side by side.

Usage:
    cd ai-backend
    uv run python scripts/inspect_quiz_prereqs.py <session_id>
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402

from src.exploration_study.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION as STUDY_SESSIONS,
    QUIZZES_SUBCOLLECTION,
    get_session_repository,
)
from src.guided_exploration.services.session_repository import (  # noqa: E402
    SESSIONS_COLLECTION as GUIDED_SESSIONS,
    EXPLORATIONS_SUBCOLLECTION,
    CONVERSATIONS_SUBCOLLECTION,
)

CORPUS_PATH = (
    project_root / "data" / "study-fake-parties" / "quiz_questions.json"
)


def _load_corpus_by_question() -> dict[str, dict]:
    with open(CORPUS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {entry["question"]: entry for entry in raw}


def _short(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


_BRACKET_ID = __import__("re").compile(r"\[([a-z0-9][a-z0-9\-]*?)\]")


def _stringify_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "summary", "content", "markdown", "body"):
            if key in content and isinstance(content[key], str):
                return content[key]
        return json.dumps(content, ensure_ascii=False)[:600]
    return str(content)


def _extract_inline_position_ids(content, citation_pool: set[str]) -> set[str]:
    """Walk a SubtopicContent dict, pull all [id] markers from
    party_positions[*].content (and summary), and return those that are
    in the citation_pool. Mirrors what guided_exploration logs as exposure
    when a leaf is opened.
    """
    found: set[str] = set()
    if not isinstance(content, dict):
        return found
    for pp in content.get("party_positions") or []:
        text = pp.get("content") or "" if isinstance(pp, dict) else ""
        for m in _BRACKET_ID.findall(text):
            if m in citation_pool:
                found.add(m)
    return found


async def inspect(session_id: str) -> None:
    repo = get_session_repository()
    fs = firestore_async.client()

    # ---- 1. Study session ----
    study_doc = await fs.collection(STUDY_SESSIONS).document(session_id).get()
    if not study_doc.exists:
        print(f"ERROR: study session {session_id} not found")
        return
    s = study_doc.to_dict() or {}
    condition = s.get("condition", {}) or {}
    chat_id = condition.get("chat_id")
    positions_encountered: list[str] = condition.get(
        "positions_encountered", []
    ) or []

    print("=" * 72)
    print(f"STUDY SESSION  {session_id}")
    print("=" * 72)
    print(f"  study_id   : {s.get('study_id')}")
    print(f"  group      : {s.get('group')}")
    print(f"  state      : {s.get('state')}")
    print(f"  system     : {condition.get('system')}")
    print(f"  topic      : {condition.get('topic')}")
    print(f"  chat_id    : {chat_id}")
    print(f"  quiz_id    : {condition.get('quiz_id')}")
    print(f"  positions encountered ({len(positions_encountered)}):")
    for pid in positions_encountered:
        print(f"      - {pid}")

    # ---- 2. Quiz ----
    quizzes_col = (
        fs.collection(STUDY_SESSIONS)
        .document(session_id)
        .collection(QUIZZES_SUBCOLLECTION)
    )
    quiz_docs = [d async for d in quizzes_col.stream()]
    if not quiz_docs:
        print("\n(no quiz documents stored)")
    else:
        corpus = _load_corpus_by_question()
        encountered = set(positions_encountered)
        for qd in quiz_docs:
            q = qd.to_dict() or {}
            print()
            print("-" * 72)
            print(f"QUIZ  {q.get('id')}   status={q.get('status')}")
            print(
                f"  created_at={q.get('created_at')}   "
                f"generated_at={q.get('generated_at')}"
            )
            questions = q.get("questions", []) or []
            print(f"  questions: {len(questions)}")
            for i, question in enumerate(questions, 1):
                text = question.get("question", "")
                corpus_entry = corpus.get(text)
                if corpus_entry is None:
                    prereqs = ["<corpus match not found>"]
                    corpus_id = "?"
                else:
                    prereqs = corpus_entry.get(
                        "prerequisite_position_ids", []
                    )
                    corpus_id = corpus_entry.get("id", "?")
                missing = [p for p in prereqs if p not in encountered]
                ok = "OK " if not missing else "BAD"
                print(
                    f"    [{i:2}] {ok}  corpus={corpus_id}  "
                    f"topic={question.get('topic')}  "
                    f"overlap={question.get('is_overlap_question')}"
                )
                print(f"          Q: {_short(text)}")
                print(f"          prereqs : {prereqs}")
                if missing:
                    print(f"          MISSING : {missing}")

    if not chat_id:
        print("\n(no chat_id on session — skipping conversation dump)")
        return

    # ---- 3. Guided exploration conversation(s) ----
    print()
    print("=" * 72)
    print(f"GUIDED EXPLORATION  chat_id={chat_id}")
    print("=" * 72)

    g_doc = await fs.collection(GUIDED_SESSIONS).document(chat_id).get()
    if not g_doc.exists:
        print("(guided session doc not found — likely a baseline session)")
        return
    g = g_doc.to_dict() or {}
    print(f"  mode={g.get('mode')}  context_id={g.get('context_id')}")

    # Session-level messages
    s_msgs = g.get("messages", []) or []
    session_cited: set[str] = set()
    print(f"\n  SESSION MESSAGES ({len(s_msgs)})")
    for m in s_msgs:
        t = m.get("type")
        content = m.get("content") or ""
        line = _short(content if isinstance(content, str) else str(content))
        cite_ids = [c.get("id") for c in (m.get("citations") or []) if c.get("id")]
        for cid in cite_ids:
            session_cited.add(cid)
        print(f"    [{t}] {line}")
        if cite_ids:
            print(f"        citations: {cite_ids}")

    # Per-exploration / per-leaf conversations
    expl_col = (
        fs.collection(GUIDED_SESSIONS)
        .document(chat_id)
        .collection(EXPLORATIONS_SUBCOLLECTION)
    )
    expl_docs = [d async for d in expl_col.stream()]

    # Walk each exploration's persisted tree to build {leaf_id: status}.
    # The exposure logger only fires when a leaf is OPENED (status moves
    # pending/loaded -> started), so pregen-only leaves (status=loaded)
    # produced no real participant exposure even though their conversation
    # doc exists.
    leaf_status: dict[str, str] = {}

    def _walk(node):
        kids = node.get("children") or []
        if not kids:
            leaf_status[node["id"]] = node.get("status", "?")
            return
        for c in kids:
            _walk(c)

    for ed in expl_docs:
        tree = (ed.to_dict() or {}).get("tree") or {}
        root = tree.get("root") or {}
        _walk(root)
    print(f"\n  EXPLORATIONS: {len(expl_docs)}")
    print(f"  LEAF STATUS:")
    for lid, st in sorted(leaf_status.items()):
        opened = "OPENED" if st in {"started", "explored"} else "pregen-only"
        print(f"    - {lid}: status={st}  [{opened}]")
    for ed in expl_docs:
        e = ed.to_dict() or {}
        print(
            f"\n  >>> EXPLORATION {ed.id}  status={e.get('status')}  "
            f"query={_short(str(e.get('query', '')), 120)}"
        )
        conv_col = (
            fs.collection(GUIDED_SESSIONS)
            .document(chat_id)
            .collection(EXPLORATIONS_SUBCOLLECTION)
            .document(ed.id)
            .collection(CONVERSATIONS_SUBCOLLECTION)
        )
        conv_docs = [d async for d in conv_col.stream()]
        for cd in conv_docs:
            c = cd.to_dict() or {}
            leaf_id = c.get("leaf_id") or cd.id
            msgs = c.get("messages", []) or []
            print(f"      leaf={leaf_id}  messages={len(msgs)}")
            for m in msgs:
                role = m.get("role")
                mtype = m.get("type")
                raw = m.get("content")
                content = _stringify_content(raw)
                cits = (
                    raw.get("citations") if isinstance(raw, dict) else None
                ) or m.get("citations") or []
                cite_ids = [cc.get("id") for cc in cits if cc.get("id")]
                inline = sorted(
                    _extract_inline_position_ids(
                        raw if isinstance(raw, dict) else {},
                        {cc.get("id") for cc in cits if cc.get("id")},
                    )
                )
                print(
                    f"          - {role}/{mtype}: {_short(content, 220)}"
                )
                if cite_ids:
                    print(f"            pool: {cite_ids}")
                if inline:
                    print(f"            inline-cited: {inline}")

    # Cross-check: positions cited across conversations vs.
    # positions_encountered on the session
    leaf_cited: set[str] = set()
    leaf_cited_by_msg: list[tuple[str, str, set[str]]] = []
    for ed in expl_docs:
        conv_col = (
            fs.collection(GUIDED_SESSIONS)
            .document(chat_id)
            .collection(EXPLORATIONS_SUBCOLLECTION)
            .document(ed.id)
            .collection(CONVERSATIONS_SUBCOLLECTION)
        )
        async for cd in conv_col.stream():
            c = cd.to_dict() or {}
            leaf_id = c.get("leaf_id") or cd.id
            for m in c.get("messages", []) or []:
                raw = m.get("content")
                # follow-up messages: explicit citations list on Message
                for cit in m.get("citations") or []:
                    cid = cit.get("id")
                    if cid:
                        leaf_cited.add(cid)
                # initial_content: inline [id] inside party_positions
                if isinstance(raw, dict):
                    pool = {
                        cc.get("id")
                        for cc in raw.get("citations") or []
                        if cc.get("id")
                    }
                    inline = _extract_inline_position_ids(raw, pool)
                    leaf_cited |= inline
                    if inline:
                        snippet = _short(
                            _stringify_content(raw), 120
                        )
                        leaf_cited_by_msg.append(
                            (
                                f"leaf:{leaf_id}/{m.get('type')}",
                                snippet,
                                inline,
                            )
                        )

    all_cited = session_cited | leaf_cited
    print()
    print("=" * 72)
    print("CROSS-CHECK")
    print("=" * 72)
    print(f"  cited in session messages      : {len(session_cited)}")
    print(f"  cited in leaf conversations    : {len(leaf_cited)}")
    print(f"  cited (union)                  : {len(all_cited)}")
    print(f"  in positions_encountered       : {len(positions_encountered)}")
    only_in_convs = all_cited - set(positions_encountered)
    only_in_session = set(positions_encountered) - all_cited
    if only_in_convs:
        print(f"  in conv but NOT in encountered : {sorted(only_in_convs)}")
    if only_in_session:
        print(
            f"  in encountered but NOT cited   : {sorted(only_in_session)}"
        )
    if not only_in_convs and not only_in_session:
        print("  perfectly matched")

    # Quiz-specific check: for each quiz question prereq, which message
    # actually surfaced that position to the participant? Full content.
    print()
    print("=" * 72)
    print("QUIZ PREREQ → MESSAGE TRACE (FULL CONTENT)")
    print("=" * 72)

    # Build pid -> [(label, full_text)] index. Full text for session
    # messages = the assistant body verbatim. For leaf initial_content =
    # the party_positions[*].content blocks of the leaf the participant
    # opened (that's the surface that actually contained the [id]).
    pid_to_msgs: dict[str, list[tuple[str, str]]] = {}

    for m in s_msgs:
        body = m.get("content")
        if not isinstance(body, str):
            body = json.dumps(body, ensure_ascii=False, indent=2)
        label = f"session/{m.get('type')}"
        for cit in m.get("citations") or []:
            cid = cit.get("id")
            if cid:
                pid_to_msgs.setdefault(cid, []).append((label, body))

    # Walk leaf conversations again to grab the party_positions content
    # for any inline [id] that matched the citation pool.
    for ed in expl_docs:
        conv_col = (
            fs.collection(GUIDED_SESSIONS)
            .document(chat_id)
            .collection(EXPLORATIONS_SUBCOLLECTION)
            .document(ed.id)
            .collection(CONVERSATIONS_SUBCOLLECTION)
        )
        async for cd in conv_col.stream():
            c = cd.to_dict() or {}
            leaf_id = c.get("leaf_id") or cd.id
            for m in c.get("messages", []) or []:
                raw = m.get("content")
                if not isinstance(raw, dict):
                    continue
                pool = {
                    cc.get("id")
                    for cc in raw.get("citations") or []
                    if cc.get("id")
                }
                for pp in raw.get("party_positions") or []:
                    if not isinstance(pp, dict):
                        continue
                    text = pp.get("content") or ""
                    party = pp.get("party", "?")
                    ids_here = {
                        m for m in _BRACKET_ID.findall(text) if m in pool
                    }
                    status = leaf_status.get(leaf_id, "?")
                    open_tag = (
                        "OPENED" if status in {"started", "explored"}
                        else "pregen-only"
                    )
                    label = (
                        f"leaf:{leaf_id} ({party}) [{open_tag}] /{m.get('type')}"
                    )
                    body = text
                    for cid in ids_here:
                        pid_to_msgs.setdefault(cid, []).append((label, body))

    # Walk the quiz and dump
    corpus = _load_corpus_by_question()
    seen_labels: set[tuple[int, str]] = set()  # (qnum, label) dedupe
    for qd in quiz_docs:
        q = qd.to_dict() or {}
        for i, question in enumerate(q.get("questions", []) or [], 1):
            text = question.get("question", "")
            corpus_entry = corpus.get(text)
            corpus_id = corpus_entry.get("id", "?") if corpus_entry else "?"
            prereqs = (
                corpus_entry.get("prerequisite_position_ids", [])
                if corpus_entry
                else []
            )
            options = question.get("options") or []
            correct_idx = question.get("correct_index")
            print()
            print("-" * 72)
            print(f"Q{i}  corpus={corpus_id}  prereqs={prereqs}")
            print(f"  Question: {text}")
            for oi, opt in enumerate(options):
                marker = "*" if oi == correct_idx else " "
                print(f"    {marker} [{oi}] {opt}")
            for pid in prereqs:
                hits = pid_to_msgs.get(pid, [])
                print()
                print(f"  >>> Prereq {pid} — {len(hits)} citation(s)")
                if not hits:
                    print("      (NEVER cited in any message)")
                    continue
                # Dedupe by label within this question so we don't print
                # the same exact source twice
                seen_here: set[str] = set()
                for label, body in hits:
                    if label in seen_here:
                        continue
                    seen_here.add(label)
                    print(f"      [{label}]")
                    for line in body.splitlines() or [""]:
                        print(f"        {line}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id")
    args = parser.parse_args()
    asyncio.run(inspect(args.session_id))


if __name__ == "__main__":
    main()
