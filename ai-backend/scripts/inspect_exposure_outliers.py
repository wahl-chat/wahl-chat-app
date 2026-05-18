#!/usr/bin/env python3
"""Dump per-participant InformationExposure for arms A and B and flag
outliers (Tukey 1.5×IQR fences) so we can see which sessions blow up
the variance.

Usage:
    cd ai-backend
    uv run python scripts/inspect_exposure_outliers.py \\
        --study 0be379bb-fc01-40dd-b21c-795199053dc2
"""

import argparse
import asyncio
import statistics
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.firebase_service import db  # noqa: E402, F401
from firebase_admin import firestore_async  # noqa: E402


STUDY_SESSIONS = "exploration_study_sessions"


def _arm_for_group(group: str) -> str | None:
    if group in ("A1", "A2"):
        return "a"
    if group in ("B1", "B2"):
        return "b"
    if group in ("C1", "C2"):
        return "c"
    return None


def _summarise(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    s = sorted(values)
    n = len(s)

    def _q(p: float) -> float:
        i = (n - 1) * p
        lo = int(i)
        hi = min(lo + 1, n - 1)
        return s[lo] + (s[hi] - s[lo]) * (i - lo)

    q1, q3 = _q(0.25), _q(0.75)
    iqr = q3 - q1
    return {
        "n": n,
        "mean": statistics.mean(s),
        "sd": statistics.stdev(s) if n > 1 else 0.0,
        "min": s[0],
        "max": s[-1],
        "median": statistics.median(s),
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "lo_fence": q1 - 1.5 * iqr,
        "hi_fence": q3 + 1.5 * iqr,
    }


async def scan(study_id: str | None) -> None:
    fs = firestore_async.client()
    coll = fs.collection(STUDY_SESSIONS)
    query = coll.where("state", "==", "complete")
    if study_id:
        query = query.where("study_id", "==", study_id)

    rows: list[dict] = []
    async for d in query.stream():
        s = d.to_dict() or {}
        arm = _arm_for_group(s.get("group", ""))
        if arm not in ("a", "b"):
            continue
        cond = s.get("condition") or {}
        exposure = len(cond.get("positions_encountered") or [])
        rows.append({
            "sid": d.id,
            "arm": arm,
            "group": s.get("group"),
            "topic": cond.get("topic"),
            "exposure": exposure,
        })

    for arm in ("a", "b"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        vals = [r["exposure"] for r in arm_rows]
        st = _summarise(vals)
        label = "A (Structured)" if arm == "a" else "B (Long Chat)"
        print(f"\n=== {label} — n={st['n']} ===")
        if st["n"] == 0:
            continue
        print(
            f"mean={st['mean']:.2f}  sd={st['sd']:.2f}  "
            f"min={st['min']}  q1={st['q1']:.1f}  med={st['median']}  "
            f"q3={st['q3']:.1f}  max={st['max']}  "
            f"IQR={st['iqr']:.1f}"
        )
        print(
            f"Tukey fences (1.5×IQR): "
            f"[{st['lo_fence']:.2f}, {st['hi_fence']:.2f}]"
        )

        arm_rows.sort(key=lambda r: r["exposure"])
        print(f"{'session':<38} {'grp':<3} {'topic':<14} {'exp':>4}  flag")
        for r in arm_rows:
            flag = ""
            if r["exposure"] < st["lo_fence"]:
                flag = "LOW-OUTLIER"
            elif r["exposure"] > st["hi_fence"]:
                flag = "HIGH-OUTLIER"
            print(
                f"{r['sid']:<38} {r['group']:<3} "
                f"{(r['topic'] or '—'):<14} "
                f"{r['exposure']:>4}  {flag}"
            )

    # Contribution to variance: which rows would, if removed, shrink SD most?
    print("\n=== Variance-leverage (drop-one effect on SD) ===")
    for arm in ("a", "b"):
        arm_rows = [r for r in rows if r["arm"] == arm]
        vals = [r["exposure"] for r in arm_rows]
        if len(vals) < 3:
            continue
        base_sd = statistics.stdev(vals)
        leverages = []
        for i, r in enumerate(arm_rows):
            rest = vals[:i] + vals[i + 1:]
            drop_sd = statistics.stdev(rest)
            leverages.append((base_sd - drop_sd, r))
        leverages.sort(key=lambda x: -x[0])
        label = "A (Structured)" if arm == "a" else "B (Long Chat)"
        print(
            f"\n{label}: base SD = {base_sd:.2f}. "
            f"Top 5 SD-shrinking removals:"
        )
        for delta, r in leverages[:5]:
            print(
                f"  drop {r['sid']} ({r['group']}, exp={r['exposure']}) "
                f"→ SD shrinks by {delta:.2f}"
            )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--study", default=None, help="Restrict to one study_id")
    args = p.parse_args()
    asyncio.run(scan(args.study))


if __name__ == "__main__":
    main()
