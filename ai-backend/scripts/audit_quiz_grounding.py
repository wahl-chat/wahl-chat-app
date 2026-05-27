"""Generate (question, grounding-claim) pairs for a grounding/ambiguity audit.

For every quiz question in ``quiz_questions.json`` this resolves its
``prerequisite_position_ids`` to the full position records (claim + argument
from the party manifestos) and emits a paired record. The output is meant to
be fed to a reviewing agent that checks, for each question:

  1. Grounding   — is the correct option actually supported by the
                   prerequisite claim(s)?
  2. Distractors — are the wrong options genuinely NOT the party's position
                   (and not strawmen no party would hold)?
  3. Unambiguity — is exactly one option defensibly correct given the claims?

This is deliberately standalone: it reads only the JSON data files and has
no dependency on the backend, an LLM client, or any API key.

Usage:
    python scripts/audit_quiz_grounding.py             # write JSON + Markdown
    python scripts/audit_quiz_grounding.py --stdout    # also print Markdown
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "study-fake-parties"
CORPUS_PATH = DATA_DIR / "quiz_questions.json"
POSITIONS_DIR = DATA_DIR / "positions"
OUT_JSON = DATA_DIR / "quiz_grounding_pairs.json"
OUT_MD = DATA_DIR / "quiz_grounding_pairs.md"


def load_positions() -> dict[str, dict[str, Any]]:
    """Map every master position id to its full record."""
    positions: dict[str, dict[str, Any]] = {}
    for path in sorted(POSITIONS_DIR.glob("*.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")):
            positions[rec["id"]] = rec
    return positions


def build_pairs(
    corpus: list[dict[str, Any]],
    positions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pair each question with the resolved records of its prerequisites."""
    pairs: list[dict[str, Any]] = []
    for q in corpus:
        prereqs: list[dict[str, Any]] = []
        for pid in q["prerequisite_position_ids"]:
            rec = positions.get(pid)
            if rec is None:
                prereqs.append({"id": pid, "missing": True})
                continue
            prereqs.append(
                {
                    "id": pid,
                    "party_id": rec.get("party_id"),
                    "topic": rec.get("topic"),
                    "subtopic": rec.get("subtopic"),
                    "claim": rec.get("claim"),
                    "argument": rec.get("argument"),
                }
            )
        ci = q["correct_index"]
        pairs.append(
            {
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
                "correct_index": ci,
                "correct_option": q["options"][ci],
                "category": q.get("category", "retention"),
                "difficulty": q.get("difficulty", "easy"),
                "hard_pattern": q.get("hard_pattern"),
                "is_overlap_question": q.get("is_overlap_question", False),
                "topic": q.get("topic"),
                "prerequisites": prereqs,
            }
        )
    return pairs


def _tag(p: dict[str, Any]) -> str:
    tag = f"{p['category']}/{p['difficulty']}"
    if p["hard_pattern"]:
        tag += f"/{p['hard_pattern']}"
    if p["is_overlap_question"]:
        tag += " [overlap]"
    return tag


def render_md(pairs: list[dict[str, Any]]) -> str:
    """Render the pairs as a human/agent-readable Markdown document."""
    out: list[str] = [
        "# Quiz grounding & ambiguity review pairs",
        "",
        f"{len(pairs)} questions. For each: the question with its options "
        "(correct one marked) and the prerequisite position record(s) it is "
        "supposed to be grounded in.",
        "",
        "---",
        "",
    ]
    for p in pairs:
        out.append(f"## {p['id']} — {p['topic']} — {_tag(p)}")
        out.append("")
        out.append(f"**Frage:** {p['question']}")
        out.append("")
        out.append("**Optionen:**")
        for i, opt in enumerate(p["options"]):
            mark = "  ✅ korrekt" if i == p["correct_index"] else ""
            out.append(f"- [{i}] {opt}{mark}")
        out.append("")
        out.append("**Grundlage (prerequisite positions):**")
        for pr in p["prerequisites"]:
            if pr.get("missing"):
                out.append(f"- ⚠️ `{pr['id']}` — POSITION NICHT GEFUNDEN")
                continue
            out.append(
                f"- `{pr['id']}` ({pr['party_id']} · "
                f"{pr['topic']}/{pr['subtopic']})"
            )
            out.append(f"  - **Claim:** {pr['claim']}")
            out.append(f"  - **Argument:** {pr['argument']}")
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="also print the Markdown rendering to stdout",
    )
    args = parser.parse_args()

    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    positions = load_positions()
    pairs = build_pairs(corpus, positions)

    OUT_JSON.write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = render_md(pairs)
    OUT_MD.write_text(md, encoding="utf-8")

    missing = [
        (p["id"], pr["id"])
        for p in pairs
        for pr in p["prerequisites"]
        if pr.get("missing")
    ]
    print(f"Wrote {len(pairs)} pairs to:")
    print(f"  {OUT_JSON}")
    print(f"  {OUT_MD}")
    if missing:
        print(f"\n⚠️  {len(missing)} unresolved prerequisite(s):")
        for qid, pid in missing:
            print(f"  {qid} -> {pid}")
    else:
        print("\nAll prerequisite_position_ids resolved cleanly.")

    if args.stdout:
        print("\n" + md)


if __name__ == "__main__":
    main()
