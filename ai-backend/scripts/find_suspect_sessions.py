#!/usr/bin/env python3
"""
Scan completed exploration-study sessions for the
"LLM-aided participant" fingerprint:

  - high user-message count during the task
  - perfect / near-perfect quiz score
  - quiz answered very fast (low total response time)
  - task duration close to the 7-minute minimum

Usage:
    cd ai-backend
    uv run python scripts/find_suspect_sessions.py [--study STUDY_ID]
"""

import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402


STUDY_SESSIONS = "exploration_study_sessions"
QUIZ_SUBMISSIONS = "quiz_submissions"
GUIDED_SESSIONS = "guided_exploration_sessions"


def _iso_to_seconds(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    from datetime import datetime

    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return (tb - ta).total_seconds()
    except Exception:
        return None


async def _count_user_messages(
    fs, chat_id: str | None
) -> dict:
    """Return per-session message metrics.

    Keys: total, typed, think_med, think_fast_frac.

    ``think_med`` is the median seconds between the assistant message
    that just finished streaming and the next user message — pure
    "reading time". ``think_fast_frac`` is the fraction of those gaps
    that were <5s when the assistant body was >=400 chars (i.e.
    couldn't plausibly have been read).
    """
    from datetime import datetime
    import statistics

    blank = {
        "total": None,
        "typed": None,
        "think_med": None,
        "think_fast_frac": None,
    }
    if not chat_id:
        return blank
    g = (await fs.collection(GUIDED_SESSIONS).document(chat_id).get()).to_dict()
    if g is None:
        return blank

    total = 0
    typed = 0
    think_secs: list[float] = []
    fast_after_long: list[bool] = []

    def _ts(m: dict) -> datetime | None:
        ts = m.get("timestamp") or m.get("created_at") or m.get("time")
        if not isinstance(ts, str):
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None

    def _walk(stream: list[dict], role_key: str, role_val: str) -> None:
        nonlocal total, typed
        prev_chips: list[str] = []
        prev_assist_ts: datetime | None = None
        prev_assist_len: int = 0
        for m in stream:
            r = m.get(role_key)
            if r == role_val:
                total += 1
                content = m.get("content")
                if isinstance(content, str):
                    hit = any(content.strip() == c.strip() for c in prev_chips)
                    if not hit:
                        typed += 1
                else:
                    typed += 1
                ts = _ts(m)
                if prev_assist_ts and ts:
                    dt = (ts - prev_assist_ts).total_seconds()
                    if dt >= 0:
                        think_secs.append(dt)
                        if prev_assist_len >= 400:
                            fast_after_long.append(dt < 5.0)
                prev_assist_ts = None
            else:
                prev_chips = m.get("suggested_followups") or []
                prev_assist_ts = _ts(m)
                c = m.get("content")
                prev_assist_len = len(c) if isinstance(c, str) else 0

    _walk(g.get("messages") or [], "type", "user")

    expl = fs.collection(GUIDED_SESSIONS).document(chat_id).collection(
        "explorations"
    )
    async for ed in expl.stream():
        convs = ed.reference.collection("conversations")
        async for cd in convs.stream():
            _walk(
                (cd.to_dict() or {}).get("messages") or [], "role", "user"
            )

    return {
        "total": total,
        "typed": typed,
        "think_med": statistics.median(think_secs) if think_secs else None,
        "think_fast_frac": (
            sum(fast_after_long) / len(fast_after_long)
            if fast_after_long
            else None
        ),
    }


async def _latest_submission(fs, session_id: str) -> dict | None:
    subs = (
        fs.collection(STUDY_SESSIONS)
        .document(session_id)
        .collection(QUIZ_SUBMISSIONS)
    )
    latest = None
    latest_ts = ""
    async for d in subs.stream():
        sub = d.to_dict() or {}
        ts = sub.get("submitted_at") or ""
        if latest is None or ts > latest_ts:
            latest = sub
            latest_ts = ts
    return latest


async def scan(study_id: str | None) -> None:
    fs = firestore_async.client()
    coll = fs.collection(STUDY_SESSIONS)
    query = coll.where("state", "==", "complete")
    if study_id:
        query = query.where("study_id", "==", study_id)

    sessions = [d async for d in query.stream()]
    print(f"Scanning {len(sessions)} complete sessions...\n")

    rows: list[dict] = []
    for d in sessions:
        s = d.to_dict() or {}
        sid = d.id
        cond = s.get("condition") or {}
        chat_id = cond.get("chat_id")
        task_secs = _iso_to_seconds(
            cond.get("started_at"), cond.get("ended_at")
        )
        sub = await _latest_submission(fs, sid)
        if not sub:
            continue
        total_q = sub.get("total_questions") or 0
        total_c = sub.get("total_correct") or 0
        score = (total_c / total_q) if total_q else None
        rts = [a.get("response_time_ms") for a in sub.get("answers") or []]
        quiz_total_ms = sum(r for r in rts if r is not None)
        quiz_avg_ms = (quiz_total_ms / len(rts)) if rts else None
        msg_stats = await _count_user_messages(fs, chat_id)

        rows.append({
            "sid": sid,
            "group": s.get("group"),
            "topic": cond.get("topic"),
            "system": cond.get("system"),
            "task_secs": task_secs,
            "n_user": msg_stats["total"],
            "n_typed": msg_stats["typed"],
            "think_med": msg_stats["think_med"],
            "think_fast_frac": msg_stats["think_fast_frac"],
            "n_positions": len(cond.get("positions_encountered") or []),
            "score": score,
            "total_c": total_c,
            "total_q": total_q,
            "quiz_total_ms": quiz_total_ms,
            "quiz_avg_ms": quiz_avg_ms,
        })

    # Suspicion = high score + low think-time on long assistant
    # responses (i.e. they couldn't have read what they were "exploring").
    def suspicion(r: dict) -> float:
        s = 0.0
        if r.get("score") and r["score"] >= 0.9:
            s += 4 * r["score"]
        ff = r.get("think_fast_frac")
        if ff is not None:
            s += ff * 6
        if r.get("think_med") is not None and r["think_med"] < 5:
            s += (5 - r["think_med"])
        if r.get("quiz_avg_ms") and r["quiz_avg_ms"] < 8000:
            s += (8000 - r["quiz_avg_ms"]) / 2000
        return s

    rows.sort(key=suspicion, reverse=True)

    print(
        f"{'session':<38} {'grp':<3} {'topic':<14} {'task':>7} "
        f"{'typed':>5} {'msgs':>4} {'think':>6} {'fast%':>5} "
        f"{'pos':>3} {'score':>6} {'avg/q':>7}  flags"
    )
    print("-" * 140)
    for r in rows:
        ts = (
            f"{int(r['task_secs'] // 60)}:"
            f"{int(r['task_secs'] % 60):02d}"
            if r["task_secs"] is not None
            else "—"
        )
        score_s = (
            f"{int(round(r['score'] * 100))}%"
            if r["score"] is not None
            else "—"
        )
        avg_s = (
            f"{int(r['quiz_avg_ms']/1000)}s" if r["quiz_avg_ms"] else "—"
        )
        think_s = (
            f"{r['think_med']:.1f}s" if r["think_med"] is not None else "—"
        )
        fast_s = (
            f"{int(r['think_fast_frac']*100)}%"
            if r["think_fast_frac"] is not None
            else "—"
        )
        flags = []
        if r.get("score") == 1.0:
            flags.append("PERFECT")
        elif r.get("score") and r["score"] >= 0.9:
            flags.append("HIGH-SCORE")
        if r.get("quiz_avg_ms") and r["quiz_avg_ms"] < 8000:
            flags.append("FAST-QUIZ")
        if r.get("think_fast_frac") and r["think_fast_frac"] >= 0.5:
            flags.append("UNREAD")
        if r.get("task_secs") and r["task_secs"] < 7.5 * 60:
            flags.append("MIN-TIME")
        print(
            f"{r['sid']:<38} {str(r['group'] or '—'):<3} "
            f"{(r['topic'] or '—'):<14} {ts:>7} "
            f"{(r['n_typed'] or 0):>5} {(r['n_user'] or 0):>4} "
            f"{think_s:>6} {fast_s:>5} "
            f"{r['n_positions']:>3} "
            f"{score_s:>6} {avg_s:>7}  {' '.join(flags)}"
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", default=None, help="Restrict to one study_id")
    args = p.parse_args()
    asyncio.run(scan(args.study))


if __name__ == "__main__":
    main()
