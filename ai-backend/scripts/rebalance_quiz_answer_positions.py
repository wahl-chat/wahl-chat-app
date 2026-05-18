#!/usr/bin/env python3
"""Rebalance the quiz corpus so the correct answer is roughly evenly
distributed across the three option positions.

Before this script ran the corpus was heavily skewed (~84% of correct
answers at index 0), making "always click A" an ~84% guessing strategy
that compromises construct validity of the knowledge-retention measure.

Permutations are deterministic given the seed below — re-running the
script produces the same output.

Usage:
    cd ai-backend
    uv run python scripts/rebalance_quiz_answer_positions.py
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

CORPUS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data" / "study-fake-parties" / "quiz_questions.json"
)
SEED = "rebalance-2026-05-18"


def _target_assignments(n: int, rng: random.Random) -> list[int]:
    """Return ``n`` target indices in {0,1,2} as evenly split as possible.

    For n=56 → 19/19/18. Order is shuffled so the rebalancing isn't
    correlated with the original corpus order.
    """
    base = [i % 3 for i in range(n)]
    rng.shuffle(base)
    return base


def main() -> None:
    with CORPUS_PATH.open(encoding="utf-8") as f:
        corpus = json.load(f)

    before = Counter(q["correct_index"] for q in corpus)
    n = len(corpus)
    rng = random.Random(SEED)

    # Sort by id so the assignment is reproducible regardless of file order.
    corpus_sorted = sorted(corpus, key=lambda q: q["id"])
    targets = _target_assignments(n, rng)

    new_by_id: dict[str, dict] = {}
    for q, target in zip(corpus_sorted, targets):
        options: list[str] = list(q["options"])
        ci = q["correct_index"]
        if not (0 <= ci < len(options)) or len(options) != 3:
            raise ValueError(
                f"Question {q['id']} has unexpected shape: "
                f"correct_index={ci} options={options}"
            )
        correct_text = options[ci]
        distractors = [opt for i, opt in enumerate(options) if i != ci]
        # Randomize the two distractors so their relative order isn't
        # always preserved by the rebalance.
        rng.shuffle(distractors)
        other_positions = [i for i in range(3) if i != target]
        new_options = [""] * 3
        new_options[target] = correct_text
        new_options[other_positions[0]] = distractors[0]
        new_options[other_positions[1]] = distractors[1]
        new_q = dict(q)
        new_q["options"] = new_options
        new_q["correct_index"] = target
        new_by_id[q["id"]] = new_q

    # Preserve the original file order on disk.
    new_corpus = [new_by_id[q["id"]] for q in corpus]
    after = Counter(q["correct_index"] for q in new_corpus)

    with CORPUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(new_corpus, f, ensure_ascii=False, indent=2)
        f.write("\n")

    def _fmt(c: Counter) -> str:
        return " ".join(
            f"idx{k}={c.get(k, 0)} ({c.get(k, 0)/n*100:.1f}%)"
            for k in (0, 1, 2)
        )

    print(f"Total questions: {n}")
    print(f"Before: {_fmt(before)}")
    print(f"After:  {_fmt(after)}")


if __name__ == "__main__":
    main()
