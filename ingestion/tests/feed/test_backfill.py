# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ingestion.feed import backfill
from ingestion.feed.builder import compute_input_hash
from ingestion.feed.bulk import WindowSources
from ingestion.feed.parliaments import PARLIAMENTS

BUNDESTAG = PARLIAMENTS["bundestag"]


def _vote(poll_id: int, day: str) -> dict:
    return {"external_id": poll_id, "publish_date": day, "content_hash": f"v{poll_id}"}


def test_a_target_mismatch_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    problems = backfill.check_target("prod", "https://cluster.example.cloud")
    assert any("ENV is 'dev'" in p for p in problems)
    assert any("wahlchat_chunks_" in p for p in problems)


def test_a_local_qdrant_is_refused_for_a_deployed_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "dev")
    problems = backfill.check_target("dev", "http://localhost:6333")
    assert any("local store" in p for p in problems)
    assert backfill.check_target("dev", "https://cluster.example.cloud") == []


def test_a_key_file_of_another_project_is_refused(tmp_path: Path) -> None:
    key = tmp_path / "key.json"
    key.write_text(json.dumps({"project_id": "wahl-chat-dev"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="not 'wahl-chat'"):
        backfill.firestore_for("prod", key)


def test_the_plan_marks_days_built_from_the_same_sources_as_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    votes = [_vote(1, "2026-10-22"), _vote(2, "2026-09-03")]
    monkeypatch.setattr(
        backfill,
        "load_sources",
        lambda *_, **__: WindowSources(
            (date(2026, 9, 1), date(2026, 10, 22)), votes, {}
        ),
    )
    existing = {"bundestag_2026-10-22": compute_input_hash([votes[0]], None)}
    plan = backfill.plan_parliament(None, BUNDESTAG, 56, existing)  # type: ignore[arg-type]
    assert [(d.day.isoformat(), d.stored) for d in plan.days] == [
        ("2026-10-22", True),
        ("2026-09-03", False),
    ]
    assert plan.to_build == 1
    lines = backfill.format_plan(plan)
    assert "stored=1 to_build=1" in lines[0]
    assert any("2026-W36" in line and "to_build=1" in line for line in lines)


def test_a_parliament_without_corpus_data_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backfill, "load_sources", lambda *_, **__: None)
    plan = backfill.plan_parliament(None, BUNDESTAG, 56, {})  # type: ignore[arg-type]
    assert [line.strip() for line in backfill.format_plan(plan)] == [
        "bundestag  no corpus data"
    ]


def test_prod_needs_the_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    assert backfill._confirm("prod", True, "wahl-chat")
    assert not backfill._confirm("prod", True, "wahl-chat-dev")
    answers: list[Any] = iter(["y"])  # type: ignore[assignment]
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert not backfill._confirm("prod", True, None)
