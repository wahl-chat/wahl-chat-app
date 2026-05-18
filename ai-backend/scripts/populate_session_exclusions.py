#!/usr/bin/env python3
"""Seed the admin exclusion tags from a heuristic pass over Firestore.

Two cohorts are tagged automatically:

1. ``potential_cheater`` — either of:
     (a) quiz score == 100% AND at least one of (quiz avg < 8s/q, task
         < 7.5 min, fast-read frac >= 50%, <= 2 typed user msgs, median
         dwell-after-assistant < 10s/msg); OR
     (b) "rusher" fingerprint: task < 2 min AND quiz avg < 3s/q AND
         (fast-read frac >= 0.8 OR not enough long-assistant gaps to
         measure but score >= 50%). These bypassed the 7-min timer via
         the dev-skip click and answered the quiz instantly.

2. ``low_engagement`` — Structured Exploration (group A1/A2) and not
   already flagged as cheater, with task time < 5 min OR <= 2 typed
   user messages OR <= 3 positions encountered.

Run is idempotent: re-running overwrites only the entries it owns.
Manually-set tags for other sessions are preserved.

Usage:
    cd ai-backend
    uv run python scripts/populate_session_exclusions.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402


STUDY_SESSIONS = "exploration_study_sessions"
QUIZ_SUBMISSIONS = "quiz_submissions"
GUIDED_SESSIONS = "guided_exploration_sessions"

EXCLUSIONS_PATH = (
    project_root.parent / "study-admin" / "data" / "session_exclusions.json"
)

# Thresholds.
CHEAT_QUIZ_AVG_MS = 8000
CHEAT_TASK_SECS = 7.5 * 60
CHEAT_FAST_FRAC = 0.5
CHEAT_TYPED_MAX = 2
# Median seconds between an assistant message and the next user message.
# Below this, the participant is plausibly skimming rather than reading.
CHEAT_DWELL_MED_SECS = 10.0

LOWENG_TASK_SECS = 5 * 60
LOWENG_TYPED_MAX = 2
LOWENG_POS_MAX = 3


def _iso_to_seconds(a: str | None, b: str | None) -> float | None:
    if not a or not b:
        return None
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return (tb - ta).total_seconds()
    except Exception:
        return None


def _ts(m: dict) -> datetime | None:
    ts = m.get("timestamp") or m.get("created_at") or m.get("time")
    if not isinstance(ts, str):
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


async def _msg_stats(fs, chat_id: str | None) -> dict:
    blank = {"typed": 0, "think_fast_frac": None, "dwell_med": None}
    if not chat_id:
        return blank
    g = (await fs.collection(GUIDED_SESSIONS).document(chat_id).get()).to_dict()
    if g is None:
        return blank

    typed = 0
    fast_after_long: list[bool] = []
    dwell: list[float] = []

    def _walk(stream: list[dict], role_key: str, role_val: str) -> None:
        nonlocal typed
        prev_chips: list[str] = []
        prev_assist_ts: datetime | None = None
        prev_assist_len: int = 0
        for m in stream:
            r = m.get(role_key)
            if r == role_val:
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
                    if 0 <= dt < 600:
                        dwell.append(dt)
                    if dt >= 0 and prev_assist_len >= 400:
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
            _walk((cd.to_dict() or {}).get("messages") or [], "role", "user")

    return {
        "typed": typed,
        "think_fast_frac": (
            sum(fast_after_long) / len(fast_after_long)
            if fast_after_long
            else None
        ),
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


async def collect_metrics(study_id: str | None) -> list[dict]:
    fs = firestore_async.client()
    coll = fs.collection(STUDY_SESSIONS)
    q = coll.where("state", "==", "complete")
    if study_id:
        q = q.where("study_id", "==", study_id)
    sessions = [d async for d in q.stream()]
    rows: list[dict] = []
    for d in sessions:
        s = d.to_dict() or {}
        sid = d.id
        cond = s.get("condition") or {}
        chat_id = cond.get("chat_id")
        task_secs = _iso_to_seconds(cond.get("started_at"), cond.get("ended_at"))
        sub = await _latest_submission(fs, sid)
        if sub:
            total_q = sub.get("total_questions") or 0
            total_c = sub.get("total_correct") or 0
            score = (total_c / total_q) if total_q else None
            rts = [a.get("response_time_ms") for a in sub.get("answers") or []]
            quiz_avg_ms = statistics.mean(
                [r for r in rts if r is not None]
            ) if rts else None
        else:
            score = None
            quiz_avg_ms = None
        msg = await _msg_stats(fs, chat_id)
        rows.append(
            {
                "sid": sid,
                "group": s.get("group"),
                "task_secs": task_secs,
                "typed": msg["typed"],
                "think_fast_frac": msg["think_fast_frac"],
                "dwell_med": msg["dwell_med"],
                "n_positions": len(cond.get("positions_encountered") or []),
                "score": score,
                "quiz_avg_ms": quiz_avg_ms,
            }
        )
    return rows


def classify(rows: list[dict]) -> dict[str, dict]:
    """Return {session_id: {reasons, note}} for sessions that hit a rule."""
    out: dict[str, dict] = {}
    for r in rows:
        sid = r["sid"]
        score = r["score"]
        cheater_signals: list[str] = []
        if score == 1.0:
            if r["quiz_avg_ms"] is not None and r["quiz_avg_ms"] < CHEAT_QUIZ_AVG_MS:
                cheater_signals.append(
                    f"quiz avg {r['quiz_avg_ms']/1000:.1f}s/q"
                )
            if r["task_secs"] is not None and r["task_secs"] < CHEAT_TASK_SECS:
                cheater_signals.append(
                    f"task {int(r['task_secs']//60)}:{int(r['task_secs']%60):02d}"
                )
            if (
                r["think_fast_frac"] is not None
                and r["think_fast_frac"] >= CHEAT_FAST_FRAC
            ):
                cheater_signals.append(
                    f"fast-read {int(r['think_fast_frac']*100)}%"
                )
            if (r["typed"] or 0) <= CHEAT_TYPED_MAX:
                cheater_signals.append(f"{r['typed'] or 0} typed msgs")
            if (
                r["dwell_med"] is not None
                and r["dwell_med"] < CHEAT_DWELL_MED_SECS
            ):
                cheater_signals.append(
                    f"dwell median {r['dwell_med']:.1f}s/msg"
                )
        # Rusher fingerprint: bypassed timer + instant quiz, regardless
        # of the final score. Anyone finishing the whole task in under
        # two minutes used the dev-skip click; sub-3s/q quizzes show
        # they didn't read the questions either.
        if (
            r["task_secs"] is not None
            and r["task_secs"] < 120
            and r["quiz_avg_ms"] is not None
            and r["quiz_avg_ms"] < 3000
        ):
            ff_hi = (
                r["think_fast_frac"] is not None
                and r["think_fast_frac"] >= 0.8
            )
            no_long_gaps = r["think_fast_frac"] is None
            if ff_hi or (no_long_gaps and (score or 0) >= 0.5):
                cheater_signals.append(
                    "rusher: task "
                    f"{int(r['task_secs']//60)}:{int(r['task_secs']%60):02d}"
                    f" + quiz {r['quiz_avg_ms']/1000:.1f}s/q"
                )
        is_cheater = bool(cheater_signals)

        is_loweng_A = False
        loweng_signals: list[str] = []
        group = (r["group"] or "").upper()
        is_arm_A = group in {"A1", "A2"}
        if is_arm_A and not is_cheater and score != 1.0:
            if r["task_secs"] is not None and r["task_secs"] < LOWENG_TASK_SECS:
                loweng_signals.append(
                    f"task {int(r['task_secs']//60)}:{int(r['task_secs']%60):02d}"
                )
            if (r["typed"] or 0) <= LOWENG_TYPED_MAX:
                loweng_signals.append(f"{r['typed'] or 0} typed msgs")
            if r["n_positions"] <= LOWENG_POS_MAX:
                loweng_signals.append(f"{r['n_positions']} positions")
            is_loweng_A = bool(loweng_signals)

        reasons = []
        if is_cheater:
            reasons.append("potential_cheater")
        if is_loweng_A:
            reasons.append("low_engagement")
        if not reasons:
            continue
        note_bits: list[str] = []
        if is_cheater:
            prefix = "100% quiz + " if score == 1.0 else ""
            note_bits.append(
                "auto-tag: " + prefix + ", ".join(cheater_signals)
            )
        if is_loweng_A:
            note_bits.append("auto-tag (arm A): " + ", ".join(loweng_signals))
        out[sid] = {"reasons": reasons, "note": " | ".join(note_bits)}
    return out


def merge_into_file(new: dict[str, dict], dry_run: bool) -> tuple[int, int]:
    """Merge ``new`` into the on-disk JSON, returning (added, updated)."""
    EXCLUSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if EXCLUSIONS_PATH.exists():
        try:
            existing = json.loads(EXCLUSIONS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    added = 0
    updated = 0
    merged = dict(existing)
    for sid, entry in new.items():
        prev = existing.get(sid)
        if prev is None:
            added += 1
            merged[sid] = entry
            continue
        prev_reasons = set(prev.get("reasons") or [])
        entry_reasons = set(entry.get("reasons") or [])
        if prev_reasons == entry_reasons and (
            prev.get("note") or ""
        ) == entry.get("note", ""):
            continue
        # Union the reasons; let the auto-note take precedence so re-runs
        # reflect current signals, but keep any manual note appended.
        union = sorted(prev_reasons | entry_reasons)
        prev_note = (prev.get("note") or "").strip()
        new_note = entry["note"]
        if prev_note and "auto-tag" not in prev_note:
            note = f"{new_note} | manual: {prev_note}"
        else:
            note = new_note
        merged[sid] = {"reasons": union, "note": note}
        updated += 1
    if not dry_run:
        tmp = EXCLUSIONS_PATH.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(EXCLUSIONS_PATH)
    return added, updated


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying the JSON.",
    )
    p.add_argument(
        "--study",
        default=None,
        help="Restrict the scan + write to one study_id.",
    )
    args = p.parse_args()

    scope = f"study {args.study}" if args.study else "all studies"
    print(f"Collecting per-session metrics from Firestore ({scope})...")
    rows = await collect_metrics(args.study)
    print(f"  scanned {len(rows)} complete sessions")

    new_entries = classify(rows)
    cheater_n = sum(
        "potential_cheater" in v["reasons"] for v in new_entries.values()
    )
    loweng_n = sum(
        "low_engagement" in v["reasons"] for v in new_entries.values()
    )
    print(f"  {cheater_n} potential_cheater, {loweng_n} low_engagement (arm A)")

    added, updated = merge_into_file(new_entries, dry_run=args.dry_run)
    verb = "would write" if args.dry_run else "wrote"
    print(f"{verb} {added} new, {updated} updated → {EXCLUSIONS_PATH}")

    if args.dry_run:
        print("\nSample entries:")
        for sid, entry in list(new_entries.items())[:10]:
            print(f"  {sid}  {entry['reasons']}  — {entry['note']}")


if __name__ == "__main__":
    asyncio.run(main())
