# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import re
from pathlib import Path

import pytest

from src.daily_digest.parliaments import PARLIAMENTS, load_party_display
from src.daily_digest.topics import DIGEST_TOPICS, TOPIC_LABELS_DE
from src.firestore_guard import guard_firestore_target

_WEB_TOPICS = (
    Path(__file__).resolve().parents[3]
    / "web"
    / "components"
    / "topics"
    / "topics.data.ts"
)


def _web_topic_keys() -> set[str]:
    source = _WEB_TOPICS.read_text(encoding="utf-8")
    block = source.split("export const TOPIC_TITLES = {", 1)[1].split("\n};", 1)[0]
    return set(re.findall(r"^  ([a-z_]+): \{", block, flags=re.MULTILINE))


def test_digest_topics_match_the_web_topic_chips() -> None:
    assert set(DIGEST_TOPICS) - {"other"} == _web_topic_keys()


def test_every_topic_has_a_german_label() -> None:
    assert set(TOPIC_LABELS_DE) == set(DIGEST_TOPICS)


@pytest.mark.parametrize(
    "seed",
    [
        [{"party_id": "cdu", "name": "CDU", "background_color": "#000000"}],
        {"cdu": {"name": "CDU", "background_color": "#000000"}},
    ],
)
def test_load_party_display_reads_both_seed_shapes(
    tmp_path: Path, seed: object
) -> None:
    parliament = PARLIAMENTS["landtag_bw"]
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / f"parties_{parliament.party_context_id}.json").write_text(
        json.dumps(seed), encoding="utf-8"
    )
    display = load_party_display(parliament, "dev", data_dir=tmp_path)
    assert display["cdu"].name == "CDU"
    assert display["cdu"].color == "#000000"


def test_bundestag_names_the_union_fraction(tmp_path: Path) -> None:
    display = load_party_display(PARLIAMENTS["bundestag"], "dev", data_dir=tmp_path)
    assert display["cdu"].name == "CDU/CSU"


def test_guard_names_the_job_in_its_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    with pytest.raises(RuntimeError, match="the daily digest builder"):
        guard_firestore_target("the daily digest builder")
