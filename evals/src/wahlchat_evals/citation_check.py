# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""How many of the chat's citations hold, and what the repair would change.

Reads runs.json files from the web-context eval (each answer with every
document the model saw), runs the citation check on every answer and writes:

    results.md   counts per citation kind, cost and time, agreement with the
                 fact judge's findings when its judge-fact.md and key.json
                 sit next to a runs.json
    verdicts.md  every checked sentence with its verdict, for spot checks
    repaired.md  each answer before and after the repair

Imports the backend as ``src``, so it runs from ai-backend (make
eval-citation-check):

    PYTHONPATH=.:../evals/src python -m wahlchat_evals.citation_check \\
        --runs a/runs.json b/runs.json --out-dir DIR
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

# Gemini 3.1 Flash-Lite, standard API price in USD per token.
PRICE_IN = 0.25 / 1_000_000
PRICE_OUT = 1.50 / 1_000_000
KINDS = ("supported", "repointable", "other_voice", "unsupported", "nonexistent")
_PARALLEL = 4


async def check_runs(runs: list[dict[str, Any]], model: Any) -> list[dict[str, Any]]:
    from src.generic_chat import citation_check as cc

    # The judge saw 1500 characters per source; check against the same.
    cc._SOURCE_CHARS = 1500
    gate = asyncio.Semaphore(_PARALLEL)

    async def one(run: dict[str, Any]) -> dict[str, Any]:
        sources = [
            cc.Source(d["id"], str(d.get("title") or ""), str(d.get("text") or ""), _voice(d))
            for d in run["documents"]
        ]
        known = {s.id for s in sources}
        voice = {s.id: s.voice for s in sources}
        async with gate:
            try:
                result = await cc.check(run["answer"], sources, model=model)
            except Exception as exc:  # noqa: BLE001 (one failed check stays in the report)
                return {**run, "check_error": f"{type(exc).__name__}: {exc}"}
        rows = []
        for v in result.verdicts:
            kinds = cc.classify(v, known, voice)
            rows.append({
                "text": v.sentence.text, "cited": list(v.sentence.cited),
                "supporting": sorted(v.supporting), "by": v.by, "kinds": kinds,
            })
        return {
            **run, "sentences": rows, "repaired": cc.repair(run["answer"], result.verdicts, sources),
            "tokens_in": result.input_tokens, "tokens_out": result.output_tokens,
            "check_seconds": result.seconds,
        }

    return list(await asyncio.gather(*(one(r) for r in runs if r.get("answer"))))


def _voice(doc: dict[str, Any]) -> Optional[str]:
    """A party's own words carry its name; records and press are neutral.
    A speech's party is the bracket in "Name (Party)"; CSU speaks with the
    Union."""
    if doc.get("type") not in ("parliamentary_speech", "party_manifesto", "drucksache"):
        return None
    party = str(doc.get("party") or "")
    bracket = re.search(r"\(([^)]+)\)\s*$", party)
    party = (bracket.group(1) if bracket else party).strip()
    return "CDU/CSU" if party.casefold() in ("csu", "cdu") else party or None


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\wäöüß]+", " ", text.casefold()).split())


_FINDING = re.compile(r"^- (A1|A2|Beide)[^:]*:\s*(.*)$")
_QUOTED = re.compile(r"„([^“]+)“")
_NUMBER = re.compile(r"\[(\d+)")


def _overlap(piece: str, text: str) -> float:
    """Share of the piece's words found in the text."""
    words = piece.split()
    found = set(text.split())
    return sum(1 for w in words if w in found) / max(1, len(words))


def judge_findings(folder: Path) -> list[dict[str, Any]]:
    """The fact judge's findings that quote a claim with its citation."""
    judge, key = folder / "judge-fact.md", folder / "key.json"
    if not judge.exists() or not key.exists():
        return []
    order = json.loads(key.read_text())
    out: list[dict[str, Any]] = []
    question = None
    for line in judge.read_text().splitlines():
        if line.startswith("## "):
            question = line[3:].strip()
            continue
        m = _FINDING.match(line)
        if not m or question not in order:
            continue
        quotes = _QUOTED.findall(m.group(2))
        if not quotes or not _NUMBER.search(m.group(2)):
            continue
        who = m.group(1)
        variants = (
            [order[question]["Antwort 1"], order[question]["Antwort 2"]] if who == "Beide"
            else [order[question][f"Antwort {who[1]}"]]
        )
        for variant in variants:
            out.append({"question_id": question, "variant": variant, "quote": quotes[0], "finding": m.group(2)})
    return out


def agreement(findings: list[dict[str, Any]], checked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per finding: did the check flag a sentence holding the quoted claim?"""
    by_run = {(r["question_id"], r["variant"]): r for r in checked}
    out = []
    for f in findings:
        run = by_run.get((f["question_id"], f["variant"]))
        quote = re.sub(r"\[[\d,\s]+\]", " ", f["quote"])
        pieces = [p for p in (_norm(x) for x in re.split(r"…|\.\.\.", quote)) if len(p) > 8]
        hit, best = None, 0.0
        for row in (run or {}).get("sentences", []):
            text = _norm(row["text"])
            score = max((1.0 if p in text else _overlap(p, text) for p in pieces), default=0.0)
            if score > best:
                hit, best = row, score
        if best < 0.75:
            hit = None
        flagged = bool(hit) and any(k != "supported" for k in hit["kinds"].values())
        out.append({**f, "found": hit is not None, "flagged": flagged, "sentence": hit})
    return out


def _kind_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(k for r in rows for k in r["kinds"].values())


def write(out: Path, sets: dict[str, list[dict[str, Any]]], agree: list[dict[str, Any]]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Citation check: result", "", "| Set | Answers | Citations | supported | re-pointable | other voice | unsupported | nonexistent | by quote | cost/answer | s/check |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, checked in sets.items():
        ok = [r for r in checked if "sentences" in r]
        for variant in ("off", "on", None):
            mine = [r for r in ok if variant is None or r.get("variant") == variant]
            if not mine:
                continue
            counts = _kind_counts([s for r in mine for s in r["sentences"]])
            total = sum(counts.values()) or 1
            quote = sum(1 for r in mine for s in r["sentences"] if s["by"] == "quote")
            cost = sum(r["tokens_in"] * PRICE_IN + r["tokens_out"] * PRICE_OUT for r in mine) / len(mine)
            secs = sum(r["check_seconds"] for r in mine) / len(mine)
            label = f"{name} / {variant or 'all'}"
            lines.append(
                f"| {label} | {len(mine)} | {total} | "
                + " | ".join(f"{counts[k]} ({100 * counts[k] / total:.0f} %)" for k in KINDS)
                + f" | {quote} sentences | ${cost:.4f} | {secs:.1f} |"
            )
    if agree:
        found = [a for a in agree if a["found"]]
        flagged = [a for a in found if a["flagged"]]
        lines += ["", f"Fact judge's quoted findings: {len(agree)}; sentence located: {len(found)};"
                  f" also flagged by the check: {len(flagged)} of {len(found)}.", ""]
        missed = [a for a in found if not a["flagged"]]
        if missed:
            lines += ["Findings the check did not flag:", ""]
            lines += [f"- {a['question_id']} ({a['variant']}): {a['finding'][:240]}" for a in missed]
        lost = [a for a in agree if not a["found"]]
        if lost:
            lines += ["", "Findings whose sentence was not located:", ""]
            lines += [f"- {a['question_id']} ({a['variant']}): „{a['quote'][:120]}“" for a in lost]
    (out / "results.md").write_text("\n".join(lines) + "\n")

    verdicts = ["# Citation check: every checked sentence", ""]
    repaired = ["# Citation check: answers before and after the repair", ""]
    for name, checked in sets.items():
        for r in checked:
            head = f"## {name}: {r['question_id']} ({r['variant']})"
            verdicts += [head, ""]
            if "check_error" in r:
                verdicts += [r["check_error"], ""]
                continue
            for s in r["sentences"]:
                marks = ", ".join(f"[{n}] {k}" for n, k in s["kinds"].items())
                verdicts.append(f"- {s['text']}  \n  cited: {marks}; supporting: {s['supporting'] or '—'}; by {s['by']}")
            verdicts.append("")
            if r["repaired"] != r["answer"]:
                repaired += [head, "", "### before", "", r["answer"], "", "### after", "", r["repaired"], ""]
    (out / "verdicts.md").write_text("\n".join(verdicts) + "\n")
    (out / "repaired.md").write_text("\n".join(repaired) + "\n")
    (out / "checked.json").write_text(json.dumps(sets, ensure_ascii=False, indent=1))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", type=Path, nargs="+", required=True, help="runs.json files")
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    from src.core.utils import load_env
    from src.generic_chat.citation_check import build_check_model

    load_env()
    model = build_check_model()
    if model is None:
        raise SystemExit("no Gemini credentials for the check model")
    sets: dict[str, list[dict[str, Any]]] = {}
    agree: list[dict[str, Any]] = []
    for path in args.runs:
        name = path.parent.name
        checked = asyncio.run(check_runs(json.loads(path.read_text()), model))
        sets[name] = checked
        agree += agreement(judge_findings(path.parent), checked)
        print(f"{name}: {len(checked)} answers checked", flush=True)
    write(args.out_dir, sets, agree)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
