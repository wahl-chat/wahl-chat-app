# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Seed of the general context (AC-1) and the request contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.generic_chat.schemas import Anchor
from src.models.context import Context, ContextParty, ContextType
from src.routes.chat import ChatRequestDto

_SEED_DIR = Path(__file__).resolve().parents[3] / "firebase" / "firestore_data"
_IN_PARLIAMENT = {"afd", "cdu", "gruene", "linke", "spd"}
_PARTIES = _IN_PARLIAMENT | {"bsw", "fdp", "fw", "oedp", "piraten", "tierschutzpartei", "volt"}


@pytest.mark.parametrize("env", ["dev", "prod"])
def test_seed_has_the_general_bundestag_context(env: str) -> None:
    contexts = json.loads((_SEED_DIR / env / "contexts.json").read_text())
    context = Context.model_validate(contexts["bundestag-aktuell"])

    assert context.type == ContextType.GENERAL
    assert context.region_path == ["DE"]
    assert context.level == "federal"
    assert context.legislature_period_id == 161
    assert context.date is None
    assert context.is_active

    raw = json.loads((_SEED_DIR / env / "parties_bundestag-aktuell.json").read_text())
    parties = {pid: ContextParty.model_validate(p) for pid, p in raw.items()}
    assert set(parties) == _PARTIES
    assert all(p.party_id == pid for pid, p in parties.items())
    assert {pid for pid, p in parties.items() if p.is_already_in_parliament} == _IN_PARLIAMENT
    assert all(p.candidate is None for p in parties.values())


def _body(**extra: object) -> dict:
    return {"session_id": "s", "context_id": "bundestag-aktuell", "user_message": "Hallo", **extra}


def test_request_defaults() -> None:
    dto = ChatRequestDto.model_validate(_body())
    assert dto.anchor is None and dto.language == "de"


@pytest.mark.parametrize(
    "anchor",
    [
        {"feed_item_id": "bundestag_2026-11-13_d185-top20"},
        {"feed_item_id": "bundestag_2026-11-13_v6123"},
        {"feed_item_id": "landtag_st_2026-03-05_d12-zp5"},
        {"poll_id": 6123},
    ],
)
def test_request_accepts_valid_anchors(anchor: dict) -> None:
    dto = ChatRequestDto.model_validate(_body(anchor=anchor, language="en"))
    assert dto.anchor == Anchor.model_validate(anchor)
    assert dto.language == "en"


@pytest.mark.parametrize(
    "anchor",
    [
        {"feed_item_id": "../../contexts/x"},
        {"feed_item_id": "bundestag_2026-11-13_v1", "poll_id": 1},
        {"poll_id": -3},
        {},
        "bundestag_2026-11-13_v1",
    ],
)
def test_request_drops_malformed_anchors(anchor: object) -> None:
    assert ChatRequestDto.model_validate(_body(anchor=anchor)).anchor is None


def test_request_rejects_unknown_language() -> None:
    with pytest.raises(ValidationError):
        ChatRequestDto.model_validate(_body(language="fr"))
