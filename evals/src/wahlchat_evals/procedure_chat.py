# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The generic chat's agent on procedure questions, per get_process variant.

    capped    get_process returns steps plus votes, speeches and Drucksachen
    timeline  get_process returns steps only; the agent fetches the rest

Runs the real agent (model, tools, local corpus) once per question and
variant and writes the answers side by side with what each run did: tools
called, the procedure get_process landed on, whether it asked instead,
sources, time. Whether an answer states the passed version rather than the
draft, and attributes Vorblatt/Antrag framing, is read by a person.

"why" questions (optionally opened from a feed item) name the parties whose
reasons are asked for. A party counts as grounded when the answer cites one
of its sources from the vote or the procedure (tier this_item or
this_procedure); context only does not count.

Imports the backend as ``src``, so it runs from ai-backend (make
eval-procedure-chat):

    PYTHONPATH=.:../evals/src python -m wahlchat_evals.procedure_chat --out report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DATA = Path(__file__).resolve().parents[2] / "data"
QUESTIONS = DATA / "procedure_chat" / "questions.json"
DOCUMENT_QUESTIONS = DATA / "procedure_documents" / "questions.json"
VARIANTS = ("capped", "timeline")
CONTEXT_ID = "bundestag-aktuell"


@dataclass
class Run:
    question_id: str
    variant: str
    answer: str = ""
    tools: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)
    asked: bool = False
    sources: int = 0
    # "why" questions: the parties the answer explains from the vote or the
    # procedure itself.
    grounded: list[str] = field(default_factory=list)
    requests: int = 0
    seconds: float = 0.0
    error: Optional[str] = None


def load_questions(limit: Optional[int] = None) -> list[dict[str, Any]]:
    """The procedure chat set, then the Drucksache set (expected = its ids)."""
    questions = json.loads(QUESTIONS.read_text())
    for q in json.loads(DOCUMENT_QUESTIONS.read_text()):
        questions.append(
            {"id": f"doc-{q['id']}", "group": q["group"], "question": q["question"],
             "expect": q.get("vorgang_ids", [])}
        )
    return questions[:limit] if limit else questions


def verdict(question: dict[str, Any], run: Run) -> str:
    """found / asked / missed / wrong / n/a; for "why", grounded k/n."""
    expected = set(question.get("expect") or [])
    if run.error:
        return "error"
    if question.get("parties"):
        parties = question["parties"]
        return f"grounded {len(set(run.grounded) & set(parties))}/{len(parties)}"
    if expected & set(run.resolved):
        return "found"
    if run.asked:
        return "asked" if question.get("ask_ok") else "asked (needless)"
    if not expected:
        return "n/a"
    return "wrong" if run.resolved else "missed"


async def run_one(question: dict[str, Any], variant: str) -> Run:
    from pydantic_ai.messages import ModelResponse, ToolCallPart

    from src.generic_chat import agent as agent_module
    from src.generic_chat import process, tools
    from src.generic_chat.schemas import Anchor, GenericChatDeps
    from src.services.firebase_service import aget_context_by_id, aget_parties_for_context

    os.environ[process.EVIDENCE_ENV] = variant
    run = Run(question_id=question["id"], variant=variant)
    context = await aget_context_by_id(CONTEXT_ID)
    if context is None:
        run.error = f"context {CONTEXT_ID} missing"
        return run
    deps = GenericChatDeps(
        context=context,
        parties=await aget_parties_for_context(CONTEXT_ID),
        language="de",
        session_id=f"eval-{question['id']}-{variant}",
    )
    if question.get("anchor"):
        deps.anchor = await tools.resolve_anchor(deps, Anchor(feed_item_id=question["anchor"]))
    original = process.get_process

    async def recorded(deps_: Any, args: Any, **kwargs: Any) -> Any:
        result = await original(deps_, args, **kwargs)
        if result.procedure is not None:
            run.resolved.append(result.procedure.vorgang_id)
        return result

    agent_module.process.get_process = recorded  # type: ignore[assignment]
    started = time.monotonic()
    try:
        result = await agent_module.agent.run(
            question["question"],
            deps=deps,
            model=agent_module.build_model(),
            usage_limits=agent_module.USAGE_LIMITS,
        )
        run.answer = str(result.output or "")
        run.requests = result.usage.requests
        run.tools = [
            part.tool_name
            for message in result.all_messages()
            if isinstance(message, ModelResponse)
            for part in message.parts
            if isinstance(part, ToolCallPart)
        ]
    except Exception as exc:  # noqa: BLE001 (one failed run stays in the report)
        run.error = f"{type(exc).__name__}: {exc}"
    finally:
        agent_module.process.get_process = original  # type: ignore[assignment]
    run.seconds = time.monotonic() - started
    if question.get("parties"):
        run.resolved = list(dict.fromkeys([*run.resolved, *deps.scope]))
        if not run.error:
            run.grounded = grounded_parties(deps, result.all_messages(), run.answer, question["parties"])
    run.asked = bool(deps.choices) and not run.resolved
    run.sources = len(deps.sources.entries)
    return run


_CITED = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def grounded_parties(deps: Any, messages: list[Any], answer: str, parties: list[str]) -> list[str]:
    """The parties the answer cites a this_item or this_procedure source of.
    A speech names its party; a Drucksache its authoring Fraktion."""
    from pydantic_ai.messages import ToolReturnPart

    documents = list(getattr(deps.anchor.result, "documents", []) if deps.anchor else [])
    for message in messages:
        for part in getattr(message, "parts", []):
            if isinstance(part, ToolReturnPart):
                documents += getattr(part.content, "documents", None) or []
    cited = {int(n) for group in _CITED.findall(answer) for n in group.split(",")}
    names = {p.party_id: [p.name.casefold(), (p.long_name or p.name).casefold()] for p in deps.parties}
    out: set[str] = set()
    for doc in documents:
        if doc.id not in cited or doc.tier not in ("this_item", "this_procedure"):
            continue
        entry = deps.sources.entries[doc.id] if doc.id < len(deps.sources.entries) else {}
        # CSU speakers belong to the Union's Fraktion.
        party = "cdu" if entry.get("party_id") == "csu" else entry.get("party_id")
        label = (doc.party or "").casefold()
        for pid in parties:
            if party == pid or any(n and n in label for n in names.get(pid, [])):
                out.add(pid)
    return sorted(out)


def report(questions: list[dict[str, Any]], runs: dict[tuple[str, str], Run]) -> str:
    lines = ["# Procedure chat eval", ""]
    lines += ["| Variant | found | asked ok | needless ask | wrong | missed | errors | avg tools | avg sources | avg s |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for variant in VARIANTS:
        mine = [(q, runs[(q["id"], variant)]) for q in questions if (q["id"], variant) in runs]
        verdicts = [verdict(q, r) for q, r in mine]
        n = max(1, len(mine))
        lines.append(
            f"| {variant} | {verdicts.count('found')} | {verdicts.count('asked')} "
            f"| {verdicts.count('asked (needless)')} | {verdicts.count('wrong')} "
            f"| {verdicts.count('missed')} | {verdicts.count('error')} "
            f"| {sum(len(r.tools) for _, r in mine) / n:.1f} "
            f"| {sum(r.sources for _, r in mine) / n:.1f} "
            f"| {sum(r.seconds for _, r in mine) / n:.1f} |"
        )
    why = [q for q in questions if q.get("parties")]
    for variant in VARIANTS if why else ():
        mine = [(q, runs[(q["id"], variant)]) for q in why if (q["id"], variant) in runs]
        if mine:
            hit = sum(len(set(r.grounded) & set(q["parties"])) for q, r in mine)
            total = sum(len(q["parties"]) for q, _ in mine)
            lines.append(f"\nWhy ({variant}): {hit}/{total} parties grounded in the vote or procedure.")
    lines.append("")
    for q in questions:
        lines += [f"## {q['id']}: {q['question']}", f"Expected: {', '.join(q.get('expect') or []) or '—'}", ""]
        for variant in VARIANTS:
            run = runs.get((q["id"], variant))
            if run is None:
                continue
            lines += [
                f"### {variant} — {verdict(q, run)}",
                f"Tools: {', '.join(run.tools) or '—'} · resolved: {', '.join(run.resolved) or '—'}"
                f" · sources {run.sources} · {run.seconds:.1f}s",
                "",
                run.error or run.answer,
                "",
            ]
    return "\n".join(lines)


async def run_all(questions: list[dict[str, Any]], variants: tuple[str, ...]) -> dict[tuple[str, str], Run]:
    runs: dict[tuple[str, str], Run] = {}
    # One at a time: the variant is switched through the environment.
    for q in questions:
        for variant in variants:
            runs[(q["id"], variant)] = await run_one(q, variant)
            print(f"{q['id']} {variant}: {verdict(q, runs[(q['id'], variant)])}", flush=True)
    return runs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="markdown report path")
    parser.add_argument("--json", type=Path, help="raw runs as JSON")
    parser.add_argument("--limit", type=int, help="first N questions only")
    parser.add_argument("--variant", choices=VARIANTS, help="one variant only")
    parser.add_argument("--ids", help="comma-separated question ids, or a prefix like 'name-'")
    args = parser.parse_args(argv)
    # Questions and corpus text stay local: no LangSmith tracing.
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["LANGSMITH_TRACING"] = "false"
    questions = load_questions(args.limit)
    if args.ids:
        wanted = args.ids.split(",")
        questions = [q for q in questions if any(q["id"] == w or (w.endswith("-") and q["id"].startswith(w)) for w in wanted)]
    variants = (args.variant,) if args.variant else VARIANTS
    runs = asyncio.run(run_all(questions, variants))
    args.out.write_text(report(questions, runs))
    if args.json:
        args.json.write_text(json.dumps([r.__dict__ for r in runs.values()], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
