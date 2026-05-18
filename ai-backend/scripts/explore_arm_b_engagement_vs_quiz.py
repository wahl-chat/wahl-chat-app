#!/usr/bin/env python3
"""Exploratory: does per-message dwell time on the assistant predict
the quiz score in arm B (Long Chat)?

Reasoning: in the long-chat arm there is no scaffolded leaf selector, so
"engagement" reduces to how long the participant spent with each
assistant reply. If reading-time-per-turn drives retention, we should
see a positive correlation with the quiz score.

We use two dwell metrics, both restricted to arm B (codebase groups
B1+B2) in the live study:

  - ``dwell_med``  = median seconds between an assistant message and the
                     participant's next user message ("read+think" gap).
  - ``per_turn``   = task duration / number of user turns (a denser
                     "seconds spent per chat round").

Output prints Pearson + Spearman r for both metrics against the binary
quiz score, with and without the locally-tagged ``potential_cheater``
exclusions applied.

Usage:
    cd ai-backend
    uv run python scripts/explore_arm_b_engagement_vs_quiz.py [--study STUDY_ID]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime
from math import sqrt
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402


STUDY_SESSIONS = "exploration_study_sessions"
QUIZ_SUBMISSIONS = "quiz_submissions"
GUIDED_SESSIONS = "guided_exploration_sessions"
DEFAULT_STUDY = "0be379bb-fc01-40dd-b21c-795199053dc2"
EXCLUSIONS_PATH = (
    project_root.parent / "study-admin" / "data" / "session_exclusions.json"
)


def _ts(m: dict) -> datetime | None:
    ts = m.get("timestamp") or m.get("created_at") or m.get("time")
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _iso_to_seconds(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return (tb - ta).total_seconds()
    except Exception:
        return None


async def _msg_metrics(fs, chat_id: str | None) -> dict:
    blank = {"n_user": 0, "dwell_med": None}
    if not chat_id:
        return blank
    g = (await fs.collection(GUIDED_SESSIONS).document(chat_id).get()).to_dict()
    if g is None:
        return blank

    n_user = 0
    dwell: list[float] = []

    def _walk(stream: list[dict], role_key: str, role_val: str) -> None:
        nonlocal n_user
        prev_assist_ts: datetime | None = None
        for m in stream:
            r = m.get(role_key)
            if r == role_val:
                n_user += 1
                ts = _ts(m)
                if prev_assist_ts and ts:
                    dt = (ts - prev_assist_ts).total_seconds()
                    if 0 <= dt < 600:  # drop nonsensical gaps (>10 min idle)
                        dwell.append(dt)
                prev_assist_ts = None
            else:
                prev_assist_ts = _ts(m)

    _walk(g.get("messages") or [], "type", "user")
    expl = fs.collection(GUIDED_SESSIONS).document(chat_id).collection(
        "explorations"
    )
    async for ed in expl.stream():
        convs = ed.reference.collection("conversations")
        async for cd in convs.stream():
            _walk((cd.to_dict() or {}).get("messages") or [], "role", "user")

    return {
        "n_user": n_user,
        "dwell_med": statistics.median(dwell) if dwell else None,
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


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx2 = sum((x - mx) ** 2 for x in xs)
    dy2 = sum((y - my) ** 2 for y in ys)
    if dx2 == 0 or dy2 == 0:
        return None
    return num / sqrt(dx2 * dy2)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    def _ranks(vs: list[float]) -> list[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        ranks = [0.0] * len(vs)
        i = 0
        while i < len(vs):
            j = i
            while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            tied_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                ranks[order[k]] = tied_rank
            i = j + 1
        return ranks

    return _pearson(_ranks(xs), _ranks(ys))


def _summary(label: str, pairs: list[tuple[float, float]]) -> str:
    if len(pairs) < 3:
        return f"  {label}: n={len(pairs)} (insufficient)"
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    r_p = _pearson(xs, ys)
    r_s = _spearman(xs, ys)
    return (
        f"  {label}: n={len(pairs)}  "
        f"Pearson r={r_p:+.3f}  Spearman ρ={r_s:+.3f}  "
        f"(x: {min(xs):.1f}–{max(xs):.1f}, "
        f"y: {min(ys)*100:.0f}–{max(ys)*100:.0f}%)"
    )


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", default=DEFAULT_STUDY)
    args = p.parse_args()

    fs = firestore_async.client()
    q = (
        fs.collection(STUDY_SESSIONS)
        .where("state", "==", "complete")
        .where("study_id", "==", args.study)
    )
    sessions = [d async for d in q.stream()]
    print(f"Loaded {len(sessions)} complete sessions for study {args.study}")

    excluded: set[str] = set()
    if EXCLUSIONS_PATH.exists():
        raw = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
        excluded = {
            sid
            for sid, e in raw.items()
            if "potential_cheater" in (e.get("reasons") or [])
        }
    print(f"  {len(excluded)} sessions tagged as potential_cheater")

    rows_all: list[dict] = []
    for d in sessions:
        s = d.to_dict() or {}
        group = (s.get("group") or "").upper()
        if group not in {"B1", "B2"}:
            continue
        sid = d.id
        cond = s.get("condition") or {}
        sub = await _latest_submission(fs, sid)
        if not sub:
            continue
        total_q = sub.get("total_questions") or 0
        total_c = sub.get("total_correct") or 0
        if not total_q:
            continue
        score = total_c / total_q
        task_secs = _iso_to_seconds(cond.get("started_at"), cond.get("ended_at"))
        msg = await _msg_metrics(fs, cond.get("chat_id"))
        per_turn = (
            task_secs / msg["n_user"]
            if (task_secs and msg["n_user"])
            else None
        )
        rows_all.append(
            {
                "sid": sid,
                "score": score,
                "n_user": msg["n_user"],
                "dwell_med": msg["dwell_med"],
                "per_turn": per_turn,
                "excluded": sid in excluded,
            }
        )

    print(f"  → {len(rows_all)} arm-B participants with quiz submissions\n")

    def _pairs(rows: list[dict], key: str) -> list[tuple[float, float]]:
        return [(r[key], r["score"]) for r in rows if r[key] is not None]

    for label, rows in [
        ("ALL arm B", rows_all),
        ("arm B excl. potential_cheater", [r for r in rows_all if not r["excluded"]]),
    ]:
        print(f"{label} (n={len(rows)})")
        print(_summary("dwell_med (s after assistant)", _pairs(rows, "dwell_med")))
        print(_summary("per_turn  (task_secs / #user turns)", _pairs(rows, "per_turn")))
        print()

    print("Per-participant table (sorted by dwell_med):")
    rows_all.sort(key=lambda r: r["dwell_med"] or -1)
    print(
        f"  {'sid':<38} {'arm':<4} {'score':>6} "
        f"{'n_user':>6} {'dwell_med':>9} {'per_turn':>9} flags"
    )
    for r in rows_all:
        flag = "EXCL" if r["excluded"] else ""
        dwell_s = f"{r['dwell_med']:.1f}" if r["dwell_med"] is not None else "—"
        per_s = f"{r['per_turn']:.1f}" if r["per_turn"] is not None else "—"
        print(
            f"  {r['sid']:<38} {'B':<4} {r['score']*100:>5.0f}% "
            f"{r['n_user']:>6} {dwell_s:>9} {per_s:>9} {flag}"
        )


if __name__ == "__main__":
    asyncio.run(main())
