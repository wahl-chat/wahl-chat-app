# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Does Drucksache text make answers better, and how should it be reached?

For each question the same context is built four ways and answered by the
same model:

    S0  speeches + votes (what the chat has today)
    S1  S0 + procedure profiles + Drucksache overview chunks (Vorblatt, Anträge)
    S2  S0 + procedure profiles + Drucksache chunks, overview and body in one ranking
    S3  S0 + procedure profiles + overview, then the body of the best hit's procedure

Speech and vote slots are identical across strategies, the way the generic
chat's search tool fills one slot per source type. The report shows the
answers side by side with per-strategy metrics; a person reads and decides.

    python -m wahlchat_evals.procedure_documents --out report.md
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time.
if __name__ == "__main__":
    from ingestion.env_file import load_env_file

    load_env_file()

import argparse
import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from qdrant_client import QdrantClient, models

from ingestion.llm_clients import gemini
from ingestion.setup_collection import COLLECTION_NAME
from wahlchat_common.embeddings import get_embeddings

QUESTIONS = Path(__file__).resolve().parents[2] / "data" / "procedure_documents" / "questions.json"
STRATEGIES = ("S0", "S1", "S2", "S3")
MODEL = "gemini-3.7-flash"
SLOTS = {"speeches": 6, "votes": 3, "procedures": 2, "documents": 4}

_PROMPT = """Du beantwortest eine Frage zur deutschen Bundespolitik ausschließlich \
mit den nummerierten Quellen unten. Belege jede Aussage mit [n]. Wenn die Quellen \
die Frage nicht beantworten, sage das. Gib Positionen von Parteien als deren \
Positionen wieder, nicht als Tatsachen. Antworte auf Deutsch, höchstens 200 Wörter.

Frage: {question}

Quellen:
{sources}
"""


@dataclass
class Source:
    kind: str  # speech | vote | procedure | overview | body
    title: str
    text: str
    vorgang_ids: list[str]


@dataclass
class Outcome:
    strategy: str
    sources: list[Source]
    answer: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


def _search(
    qdrant: QdrantClient, vector: list[float], must: list[Any], limit: int
) -> list[dict[str, Any]]:
    hits = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        using="dense",
        query_filter=models.Filter(must=must),
        limit=limit,
        with_payload={"exclude": ["meta.sentence_map"]},
    ).points
    return [dict(h.payload or {}) for h in hits]


def _eq(key: str, value: Any) -> models.FieldCondition:
    return models.FieldCondition(key=key, match=models.MatchValue(value=value))


def _sources(kind: str, payloads: list[dict[str, Any]]) -> list[Source]:
    return [
        Source(
            kind=kind if kind != "document" else str(p.get("doc_section") or "body"),
            title=str(p.get("citation_title") or ""),
            text=str(p.get("text") or "")[:1800],
            vorgang_ids=[str(v) for v in p.get("vorgang_ids") or []],
        )
        for p in payloads
    ]


def contexts(qdrant: QdrantClient, vector: list[float]) -> dict[str, list[Source]]:
    """The four contexts for one question vector."""
    base = _sources(
        "speech", _search(qdrant, vector, [_eq("source_type", "parliamentary_speech")], SLOTS["speeches"])
    ) + _sources(
        "vote",
        _search(qdrant, vector, [_eq("source_type", "vote_record"), _eq("region", "DE")], SLOTS["votes"]),
    )
    profiles = _sources(
        "procedure", _search(qdrant, vector, [_eq("source_type", "procedure")], SLOTS["procedures"])
    )
    k = SLOTS["documents"]
    doc = [_eq("source_type", "drucksache")]
    overview = _search(qdrant, vector, [*doc, _eq("doc_section", "overview")], k)
    mixed = _search(qdrant, vector, doc, k)
    target = next((v for p in overview for v in p.get("vorgang_ids") or []), None)
    body = (
        _search(qdrant, vector, [*doc, _eq("doc_section", "body"), _eq("vorgang_ids", target)], k)
        if target
        else []
    )
    keep = max(1, k // 2)
    return {
        "S0": base,
        "S1": base + profiles + _sources("document", overview),
        "S2": base + profiles + _sources("document", mixed),
        "S3": base + profiles + _sources("document", overview[:keep] + body[: k - keep]),
    }


def _render_sources(sources: list[Source]) -> str:
    return "\n\n".join(f"[{i}] ({s.kind}) {s.title}\n{s.text}" for i, s in enumerate(sources, 1))


def _metrics(outcome: Outcome, expected: list[str]) -> dict[str, Any]:
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", outcome.answer)}
    kinds = [s.kind for s in outcome.sources]
    cited_kinds = [outcome.sources[n - 1].kind for n in cited if 0 < n <= len(outcome.sources)]
    on_target = [
        s.kind for s in outcome.sources if expected and set(s.vorgang_ids) & set(expected)
    ]
    return {
        "overview_chunks": kinds.count("overview"),
        "body_chunks": kinds.count("body"),
        "on_target_sources": len(on_target),
        "on_target_documents": sum(1 for k in on_target if k in ("overview", "body")),
        "citations": len(cited),
        "cited_documents": sum(1 for k in cited_kinds if k in ("overview", "body")),
        "cited_speeches_votes": sum(1 for k in cited_kinds if k in ("speech", "vote")),
        "answer_words": len(outcome.answer.split()),
    }


async def _answer(llm: Any, question: str, sources: list[Source]) -> str:
    message = await llm.ainvoke(_PROMPT.format(question=question, sources=_render_sources(sources)))
    content = message.content
    if isinstance(content, list):
        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
    return str(content).strip()


async def evaluate(questions: list[dict[str, Any]], *, limit: Optional[int] = None) -> list[dict[str, Any]]:
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    embed = get_embeddings(task_type="RETRIEVAL_QUERY")
    llm = gemini(MODEL, temperature=0)
    results: list[dict[str, Any]] = []
    for q in questions[:limit]:
        vector = embed.embed_query(q["question"])
        built = contexts(qdrant, vector)
        outcomes = [Outcome(s, built[s]) for s in STRATEGIES]
        answers = await asyncio.gather(*(_answer(llm, q["question"], o.sources) for o in outcomes))
        for outcome, answer in zip(outcomes, answers, strict=True):
            outcome.answer = answer
            outcome.metrics = _metrics(outcome, q.get("vorgang_ids") or [])
        results.append({**q, "outcomes": outcomes})
        print(f"{q['id']}: " + "  ".join(f"{o.strategy} {o.metrics}" for o in outcomes), flush=True)
    return results


def render(results: list[dict[str, Any]]) -> str:
    lines = ["# Drucksache experiment: S0–S3", ""]
    lines += ["| Question | Group | " + " | ".join(STRATEGIES) + " |", "|---|---|" + "---|" * len(STRATEGIES)]
    for r in results:
        cells = []
        for o in r["outcomes"]:
            m = o.metrics
            cells.append(
                f"docs {m['overview_chunks']}o/{m['body_chunks']}b · on-target {m['on_target_documents']} "
                f"· cited docs {m['cited_documents']} · cited S+V {m['cited_speeches_votes']}"
            )
        lines.append(f"| {r['id']} | {r['group']} | " + " | ".join(cells) + " |")
    lines.append("")
    for r in results:
        lines += [f"## {r['id']}: {r['question']}", ""]
        for o in r["outcomes"]:
            lines += [f"> [!example]- {o.strategy}", *[f"> {line}" for line in o.answer.splitlines()], ""]
            titles = [f"[{i}] {s.kind}: {s.title}" for i, s in enumerate(o.sources, 1) if s.kind not in ("speech", "vote")]
            if titles:
                lines += [f"> Sources beyond speeches/votes: {'; '.join(titles)}", ""]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True, help="markdown report path")
    parser.add_argument("--json", type=Path, help="raw results as JSON")
    parser.add_argument("--limit", type=int, help="first N questions only")
    args = parser.parse_args(argv)
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    results = asyncio.run(evaluate(questions, limit=args.limit))
    args.out.write_text(render(results), encoding="utf-8")
    if args.json:
        raw = [
            {**{k: v for k, v in r.items() if k != "outcomes"},
             "outcomes": [{"strategy": o.strategy, "answer": o.answer, "metrics": o.metrics,
                           "sources": [s.__dict__ for s in o.sources]} for o in r["outcomes"]]}
            for r in results
        ]
        args.json.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"report: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
