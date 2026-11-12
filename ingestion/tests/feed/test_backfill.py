# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from ingestion.feed import backfill
from ingestion.feed.bulk import WindowSources
from ingestion.feed.items import vote_input_hash
from ingestion.feed.models import FeedItem
from ingestion.feed.parliaments import PARLIAMENTS
from tests.feed.samples import sample_items

BUNDESTAG = PARLIAMENTS["bundestag"]


def _vote(poll_id: int, day: str) -> dict:
    return {"external_id": poll_id, "publish_date": day, "content_hash": f"v{poll_id}"}


def _stored(item_id: str, input_hash: str, **update: Any) -> FeedItem:
    return sample_items()[0].model_copy(
        update={"id": item_id, "input_hash": input_hash, **update}
    )


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


def test_the_plan_counts_items_built_from_the_same_sources_as_stored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    votes = [_vote(1, "2026-10-22"), _vote(2, "2026-10-22"), _vote(3, "2026-09-03")]
    seen: dict[str, Any] = {}

    def sources(*_: Any, **kwargs: Any) -> WindowSources:
        seen.update(kwargs)
        return WindowSources((date(2026, 9, 1), date(2026, 10, 22)), votes, {})

    monkeypatch.setattr(backfill, "load_sources", sources)
    stored = {
        "bundestag_2026-10-22_v1": _stored(
            "bundestag_2026-10-22_v1", vote_input_hash(votes[0])
        )
    }
    plan = backfill.plan_parliament(
        None,  # type: ignore[arg-type]
        BUNDESTAG,
        56,
        stored,
        since=date(2026, 9, 1),
    )
    assert seen == {"since": date(2026, 9, 1)}
    assert [(d.day.isoformat(), d.items, d.to_build) for d in plan.days] == [
        ("2026-10-22", 2, 1),
        ("2026-09-03", 1, 1),
    ]
    assert plan.to_build == 2
    lines = backfill.format_plan(plan)
    assert "items=3 stored=1 to_build=2" in lines[0]
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


def _deployed_run(
    monkeypatch: pytest.MonkeyPatch, to_build: int, calls: list[str]
) -> None:
    """main() against a dev target with every store and model stubbed out."""
    monkeypatch.setenv("QDRANT_URL", "https://cluster.example.cloud")
    monkeypatch.setenv("REVALIDATE_SECRET", "secret")
    monkeypatch.setattr(backfill, "check_target", lambda *_: [])
    monkeypatch.setattr(backfill, "guard_firestore_target", lambda *_, **__: None)
    monkeypatch.setattr(backfill, "firestore_for", lambda *_: (None, "stub"))
    monkeypatch.setattr(backfill, "QdrantClient", lambda **_: None)
    monkeypatch.setattr(backfill, "check_fingerprint", lambda *_: None)
    monkeypatch.setattr(backfill, "read_items_since", lambda *_: [])
    plan = backfill.ParliamentPlan(BUNDESTAG, None)
    plan.days = [backfill.DayStatus(date(2026, 10, 22), 1, to_build)]
    monkeypatch.setattr(backfill, "plan_parliament", lambda *_, **__: plan)
    monkeypatch.setattr(backfill, "_build", lambda *_: calls.append("build") or [])
    monkeypatch.setattr(
        backfill, "post_revalidate", lambda env: calls.append(f"revalidate {env}")
    )


@pytest.mark.parametrize(
    ("to_build", "expected"),
    [(2, ["build", "revalidate dev"]), (0, ["revalidate dev"])],
)
def test_a_run_busts_the_web_cache_even_with_nothing_to_build(
    monkeypatch: pytest.MonkeyPatch, to_build: int, expected: list[str]
) -> None:
    calls: list[str] = []
    _deployed_run(monkeypatch, to_build, calls)
    assert backfill.main(["--env", "dev", "--yes"]) == 0
    assert calls == expected


def test_a_plan_leaves_the_web_cache_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _deployed_run(monkeypatch, 2, calls)
    monkeypatch.delenv("REVALIDATE_SECRET")
    assert backfill.main(["--env", "dev", "--plan"]) == 0
    assert calls == []


def test_a_run_without_the_secret_is_refused_before_building(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    _deployed_run(monkeypatch, 2, calls)
    monkeypatch.delenv("REVALIDATE_SECRET")
    assert backfill.main(["--env", "dev", "--yes"]) == 2
    assert calls == []


def test_a_failed_cache_bust_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    _deployed_run(monkeypatch, 0, calls)

    def refused(_: str) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(backfill, "post_revalidate", refused)
    assert backfill.main(["--env", "dev", "--yes"]) == 4
