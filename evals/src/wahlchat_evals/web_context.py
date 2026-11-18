# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The generic chat with and without press coverage (GENERIC_CHAT_WEB_CONTEXT).

Runs the real agent on each question twice, "off" (as deployed) and "on",
and writes the pairs for judging blind: per question, the two answers in a
random order as "Antwort 1" and "Antwort 2".

    answers.md   both answers per question, labelled by variant, for reading
    fact.md      for the fact judge: question, both answers, every source text
    reader.md    for the reader judge: question and both answers as the chat
                 shows them (text and source titles, no source texts)
    key.json     which numbered answer is which variant

Imports the backend as ``src``, so it runs from ai-backend:

    PYTHONPATH=.:../evals/src python -m wahlchat_evals.web_context --out-dir DIR
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

QUESTIONS = Path(__file__).resolve().parents[2] / "data" / "web_context" / "questions.json"
VARIANTS = ("off", "on")
CONTEXT_ID = "bundestag-aktuell"
_SOURCE_TEXT_CHARS = 1500


@dataclass
class Run:
    question_id: str
    variant: str
    answer: str = ""
    tools: list[str] = field(default_factory=list)
    # Every document the model saw, by citation number.
    documents: list[dict[str, Any]] = field(default_factory=list)
    press: int = 0
    seconds: float = 0.0
    error: Optional[str] = None


async def run_one(question: dict[str, Any], variant: str) -> Run:
    from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

    from src.generic_chat import agent as agent_module
    from src.generic_chat import tools, web_context
    from src.generic_chat.schemas import Anchor, GenericChatDeps
    from src.services.firebase_service import aget_context_by_id, aget_parties_for_context

    os.environ[web_context.ENV] = variant
    run = Run(question_id=question["id"], variant=variant)
    context = await aget_context_by_id(CONTEXT_ID)
    if context is None:
        run.error = f"context {CONTEXT_ID} missing"
        return run
    deps = GenericChatDeps(
        context=context,
        parties=await aget_parties_for_context(CONTEXT_ID),
        language="de",
        session_id=f"eval-web-{question['id']}-{variant}",
    )
    started = time.monotonic()
    try:
        if question.get("anchor"):
            deps.anchor = await tools.resolve_anchor(deps, Anchor(feed_item_id=question["anchor"]))
        result = await agent_module.agent.run(
            question["question"],
            deps=deps,
            model=agent_module.build_model(),
            usage_limits=agent_module.USAGE_LIMITS,
        )
        run.answer = str(result.output or "")
        messages = result.all_messages()
        run.tools = [
            part.tool_name
            for message in messages
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, ToolCallPart)
        ]
        seen = list(getattr(deps.anchor.result, "documents", []) if deps.anchor else [])
        for message in messages:
            for part in getattr(message, "parts", []):
                if isinstance(part, ToolReturnPart):
                    seen += getattr(part.content, "documents", None) or []
        by_id = {d.id: d for d in seen}
        run.documents = [
            {
                "id": d.id, "type": d.source_type, "tier": d.tier, "title": d.title,
                "date": d.date, "party": d.party, "outlet": d.outlet,
                "text": _plain(d.text)[:_SOURCE_TEXT_CHARS],
            }
            for d in sorted(by_id.values(), key=lambda d: d.id)
        ]
        run.press = sum(1 for d in by_id.values() if d.tier == "press")
    except Exception as exc:  # noqa: BLE001 (one failed run stays in the report)
        run.error = f"{type(exc).__name__}: {exc}"
    run.seconds = time.monotonic() - started
    return run


def _plain(text: str) -> str:
    return " ".join(re.sub(r"</?web_snippet[^>]*>", "", text or "").split())


_CITED = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def cited(answer: str) -> set[int]:
    return {int(n) for group in _CITED.findall(answer) for n in group.split(",")}


def _source_line(doc: dict[str, Any]) -> str:
    who = doc.get("outlet") or doc.get("party") or ""
    return f"[{doc['id']}] {doc['type']}: {doc.get('title') or '—'} ({who}, {doc.get('date') or 'ohne Datum'})"


def write_outputs(
    questions: list[dict[str, Any]], runs: dict[tuple[str, str], Run], out: Path, seed: int
) -> None:
    rng = random.Random(seed)
    key: dict[str, dict[str, str]] = {}
    fact = ["# Faktenprüfung: Antwortpaare", ""]
    reader = ["# Leserurteil: Antwortpaare", ""]
    answers = ["# Web-Kontext: alle Antworten", ""]
    for q in questions:
        order = list(VARIANTS)
        rng.shuffle(order)
        key[q["id"]] = {"Antwort 1": order[0], "Antwort 2": order[1]}
        head = [f"## {q['id']}: {q['question']}", ""]
        if q.get("anchor"):
            head += [f"(Die Person hat den Chat aus dem Feed geöffnet, zu: {q['anchor']})", ""]
        fact += head
        reader += head
        answers += head
        for label, variant in zip(("Antwort 1", "Antwort 2"), order):
            run = runs[(q["id"], variant)]
            body = run.error or run.answer
            used = cited(run.answer)
            shown = [d for d in run.documents if d["id"] in used]
            fact += [f"### {label}", "", body, "", "Zitierte Quellen (vollständiger Text, wie das Modell ihn sah):", ""]
            for doc in shown:
                fact += [f"- {_source_line(doc)}", f"  > {doc['text']}"]
            fact.append("")
            reader += [f"### {label}", "", body, "", "Quellen unter der Antwort:", ""]
            reader += [f"- {_source_line(doc)}" for doc in shown] + [""]
        for variant in VARIANTS:
            run = runs[(q["id"], variant)]
            answers += [
                f"### {variant}: {run.press} press documents seen, tools: {', '.join(run.tools) or '—'},"
                f" {run.seconds:.1f}s",
                "",
                run.error or run.answer,
                "",
            ]
    out.mkdir(parents=True, exist_ok=True)
    (out / "fact.md").write_text("\n".join(fact))
    (out / "reader.md").write_text("\n".join(reader))
    (out / "answers.md").write_text("\n".join(answers))
    (out / "key.json").write_text(json.dumps(key, indent=2))
    (out / "runs.json").write_text(
        json.dumps([asdict(r) for r in runs.values()], ensure_ascii=False, indent=2)
    )


async def run_all(questions: list[dict[str, Any]]) -> dict[tuple[str, str], Run]:
    runs: dict[tuple[str, str], Run] = {}
    # One at a time: the variant is switched through the environment.
    for q in questions:
        for variant in VARIANTS:
            run = await run_one(q, variant)
            runs[(q["id"], variant)] = run
            print(f"{q['id']} {variant}: press={run.press} tools={run.tools} {run.error or ''}", flush=True)
    return runs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--ids", help="comma-separated question ids")
    parser.add_argument("--seed", type=int, default=7, help="answer order")
    args = parser.parse_args(argv)
    # Questions and corpus text stay local: no LangSmith tracing.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    questions = json.loads(QUESTIONS.read_text())
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    runs = asyncio.run(run_all(questions))
    write_outputs(questions, runs, args.out_dir, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
