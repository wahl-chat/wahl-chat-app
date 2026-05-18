#!/usr/bin/env python3
"""Per-question item analysis on the live study quiz.

For every quiz question that actually appeared in a submission, report:

  - ``n``         number of participants who answered it
  - ``p_value``   share who got it right (item difficulty; 0..1)
  - ``mean_R``    mean overall quiz score (%) among participants who got
                  this question right
  - ``mean_W``    mean overall quiz score (%) among participants who got
                  it wrong (abstain counts as wrong, matching scoring)
  - ``Δ``         mean_R − mean_W (a crude discrimination index)
  - ``r_pb``      point-biserial correlation between this item's
                  correctness and the participant's total score
                  (excluding the item itself).

High p_value + low Δ ≈ trivial item; negative r_pb ≈ the item is
mis-keyed or rewarding the wrong knowledge. With small n the numbers
are noisy — use them as direction, not proof.

Optional flags:
  --no-exclude    keep ``potential_cheater``-tagged participants
                  (default: drop them)
  --version vX    restrict to one corpus version
                  (``v1`` for legacy submissions with version=None,
                  or ``v2`` etc.)

Usage:
    cd ai-backend
    uv run python scripts/inspect_quiz_item_discrimination.py [--study STUDY_ID]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from math import sqrt
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402


STUDY_SESSIONS = "exploration_study_sessions"
QUIZ_SUBMISSIONS = "quiz_submissions"
QUIZZES_SUBCOLLECTION = "quizzes"
DEFAULT_STUDY = "0be379bb-fc01-40dd-b21c-795199053dc2"
EXCLUSIONS_PATH = (
    project_root.parent / "study-admin" / "data" / "session_exclusions.json"
)
CORPUS_PATH = (
    project_root / "data" / "study-fake-parties" / "quiz_questions.json"
)


def _load_corpus_index() -> dict[str, dict]:
    """Map normalised question text → corpus entry (id, topic, etc.).

    The quiz sampler mints a fresh ``uuid4`` for every per-session
    question (``quiz_sampler.py:_to_quiz_question``), so submissions
    reference per-session UUIDs rather than the stable ``q-NNN`` corpus
    ids. We recover the corpus id by matching on the question text,
    which is unique within the corpus.
    """
    raw = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for entry in raw:
        key = entry["question"].strip()
        index[key] = entry
    return index


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


async def _quiz_doc(fs, session_id: str, quiz_id: str | None) -> dict | None:
    if not quiz_id:
        return None
    doc = (
        await fs.collection(STUDY_SESSIONS)
        .document(session_id)
        .collection(QUIZZES_SUBCOLLECTION)
        .document(quiz_id)
        .get()
    )
    if not doc.exists:
        return None
    return doc.to_dict() or {}


def _quiz_version(quiz: dict | None) -> str:
    """Return ``'v1'`` (legacy / None) or whatever version the quiz doc has."""
    if not quiz:
        return "v1"
    return quiz.get("version") or "v1"


def _uuid_to_corpus_id(
    quiz: dict | None, corpus_index: dict[str, dict]
) -> dict[str, dict]:
    """Per-session map: question UUID → corpus entry (or ``None`` if unmatched)."""
    if not quiz:
        return {}
    out: dict[str, dict] = {}
    for q in quiz.get("questions") or []:
        qid = q.get("id")
        text = (q.get("question") or "").strip()
        if not qid or not text:
            continue
        entry = corpus_index.get(text)
        if entry is not None:
            out[qid] = entry
    return out


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", default=DEFAULT_STUDY)
    p.add_argument(
        "--no-exclude",
        action="store_true",
        help="Keep potential_cheater rows in the analysis.",
    )
    p.add_argument(
        "--version",
        default=None,
        help="Restrict to one corpus version (e.g. 'v1' or 'v2').",
    )
    args = p.parse_args()

    fs = firestore_async.client()
    corpus_index = _load_corpus_index()
    print(f"Loaded {len(corpus_index)} questions from local corpus")

    sessions = [
        d async for d in (
            fs.collection(STUDY_SESSIONS)
            .where("state", "==", "complete")
            .where("study_id", "==", args.study)
        ).stream()
    ]
    print(f"Loaded {len(sessions)} complete sessions for study {args.study}")

    excluded: set[str] = set()
    if not args.no_exclude and EXCLUSIONS_PATH.exists():
        raw = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
        excluded = {
            sid
            for sid, e in raw.items()
            if "potential_cheater" in (e.get("reasons") or [])
        }
        print(f"  dropping {len(excluded)} potential_cheater rows")

    # Per-participant: list of (corpus_qid, is_correct) plus the overall
    # total_correct count (for the "leave-one-out" total used in the
    # point-biserial below). The per-session quiz doc is the bridge from
    # per-session UUID → stable corpus id.
    participants: list[dict] = []
    n_unmapped = 0
    for d in sessions:
        sid = d.id
        if sid in excluded:
            continue
        s = d.to_dict() or {}
        cond = s.get("condition") or {}
        quiz_id = cond.get("quiz_id")
        sub = await _latest_submission(fs, sid)
        if not sub:
            continue
        quiz = await _quiz_doc(fs, sid, quiz_id)
        version = _quiz_version(quiz)
        if args.version and version != args.version:
            continue
        uuid_to_entry = _uuid_to_corpus_id(quiz, corpus_index)
        answers = sub.get("answers") or []
        total_q = sub.get("total_questions") or 0
        total_c = sub.get("total_correct") or 0
        if not total_q:
            continue
        per_q: list[tuple[str, dict, bool]] = []
        for a in answers:
            uuid = a.get("question_id")
            if not uuid:
                continue
            entry = uuid_to_entry.get(uuid)
            if entry is None:
                n_unmapped += 1
                continue
            per_q.append((entry["id"], entry, bool(a.get("is_correct"))))
        participants.append(
            {
                "sid": sid,
                "version": version,
                "total_q": total_q,
                "total_c": total_c,
                "per_q": per_q,
            }
        )

    print(f"  → {len(participants)} participants with submissions analysed")
    if n_unmapped:
        print(f"  ⚠ {n_unmapped} answers could not be mapped to a corpus question")
    print()

    # Bucket per-question across participants.
    by_qid: dict[str, dict] = {}
    for p_row in participants:
        for qid, q_entry, ok in p_row["per_q"]:
            entry = by_qid.setdefault(
                qid,
                {
                    "topic": q_entry.get("topic", "—"),
                    "is_overlap": bool(q_entry.get("is_overlap_question")),
                    "n": 0,
                    "n_correct": 0,
                    "score_R": [],
                    "score_W": [],
                    "pb_x": [],  # 1 if correct else 0
                    "pb_y": [],  # leave-one-out total (correct count − this)
                },
            )
            entry["n"] += 1
            # Leave-one-out total so an item isn't trivially correlated
            # with itself: subtract this item's contribution from the
            # participant's total before computing r_pb.
            loo_total = p_row["total_c"] - (1 if ok else 0)
            denom = max(p_row["total_q"] - 1, 1)
            loo_score = 100.0 * loo_total / denom
            total_score_pct = 100.0 * p_row["total_c"] / p_row["total_q"]
            if ok:
                entry["n_correct"] += 1
                entry["score_R"].append(total_score_pct)
            else:
                entry["score_W"].append(total_score_pct)
            entry["pb_x"].append(1.0 if ok else 0.0)
            entry["pb_y"].append(loo_score)

    print(f"Per-question item statistics (across {len(participants)} participants)")
    print(
        f"  {'qid':<8} {'topic':<16} {'n':>3} {'p_value':>7} "
        f"{'mean_R':>7} {'mean_W':>7} {'Δ':>6} {'r_pb':>6}  flag"
    )
    print("  " + "-" * 80)

    rows = []
    for qid, e in by_qid.items():
        n = e["n"]
        pv = e["n_correct"] / n if n else None
        mR = statistics.mean(e["score_R"]) if e["score_R"] else None
        mW = statistics.mean(e["score_W"]) if e["score_W"] else None
        delta = (mR - mW) if (mR is not None and mW is not None) else None
        r_pb = _pearson(e["pb_x"], e["pb_y"]) if n >= 3 else None
        rows.append(
            {
                "qid": qid,
                "topic": e["topic"],
                "is_overlap": e["is_overlap"],
                "n": n,
                "pv": pv,
                "mR": mR,
                "mW": mW,
                "delta": delta,
                "r_pb": r_pb,
            }
        )

    rows.sort(key=lambda r: (-(r["pv"] or 0), r["qid"]))
    for r in rows:
        pv = f"{r['pv']*100:5.1f}%" if r["pv"] is not None else "    —"
        mR = f"{r['mR']:5.1f}%" if r["mR"] is not None else "    —"
        mW = f"{r['mW']:5.1f}%" if r["mW"] is not None else "    —"
        delta = f"{r['delta']:+5.1f}" if r["delta"] is not None else "    —"
        r_pb = f"{r['r_pb']:+.2f}" if r["r_pb"] is not None else "   —"
        flag = "ov" if r["is_overlap"] else ""
        print(
            f"  {r['qid']:<8} {r['topic']:<16} {r['n']:>3} {pv:>7} "
            f"{mR:>7} {mW:>7} {delta:>6} {r_pb:>6}  {flag}"
        )

    print()
    pvs = [r["pv"] for r in rows if r["pv"] is not None]
    rpbs = [r["r_pb"] for r in rows if r["r_pb"] is not None]
    print(
        f"Difficulty summary: n_items={len(pvs)}  "
        f"mean p_value={statistics.mean(pvs)*100:.1f}%  "
        f"min={min(pvs)*100:.1f}%  max={max(pvs)*100:.1f}%"
    )
    if rpbs:
        print(
            f"Discrimination summary: mean r_pb={statistics.mean(rpbs):+.3f}  "
            f"min={min(rpbs):+.3f}  max={max(rpbs):+.3f}  "
            f"n_negative={sum(1 for r in rpbs if r < 0)}"
        )

    perfect = [r["qid"] for r in rows if r["pv"] == 1.0]
    zero = [r["qid"] for r in rows if r["pv"] == 0.0]
    if perfect:
        print(f"\nAlways-correct ({len(perfect)}): {', '.join(perfect)}")
    if zero:
        print(f"Always-wrong   ({len(zero)}): {', '.join(zero)}")


if __name__ == "__main__":
    asyncio.run(main())
