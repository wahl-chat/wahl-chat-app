# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json

from wahlchat_evals.procedure_documents import (
    QUESTIONS,
    Outcome,
    Source,
    _metrics,
    render,
)


def test_metrics_count_document_kinds_targets_and_citations() -> None:
    sources = [
        Source("speech", "Rede", "…", ["1"]),
        Source("overview", "Drucksache 21/1", "…", ["1"]),
        Source("report", "Drucksache 21/1", "…", ["2"]),
    ]
    outcome = Outcome(
        "procedures",
        sources,
        answer="Laut Vorblatt [2] und Rede [1]; [9] gibt es nicht.",
    )
    m = _metrics(outcome, ["1"])
    assert m["overview_chunks"] == 1 and m["report_chunks"] == 1
    assert m["on_target_sources"] == 2 and m["on_target_documents"] == 1
    assert m["cited_documents"] == 1 and m["cited_speeches_votes"] == 1


def test_question_set_is_well_formed() -> None:
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    assert len({q["id"] for q in questions}) == len(questions) >= 15
    assert {q["group"] for q in questions} == {"law", "position", "timeline", "general"}


def test_report_renders_every_strategy() -> None:
    outcome = Outcome("today", [], answer="Antwort")
    outcome.metrics = _metrics(outcome, [])
    out = render([{"id": "q", "group": "law", "question": "?", "outcomes": [outcome]}])
    assert "## q: ?" in out and "[!example]- today" in out
