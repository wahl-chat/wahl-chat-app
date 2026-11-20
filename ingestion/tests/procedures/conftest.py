# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Live DIP responses (2026-11-16), trimmed: Vorgang 320784 (Grundgesetz,
Schuldenbremse), 338366 (Haushaltsbegleitgesetz 2027), 341758 (Antrag Femizide),
341570 (Vereinbarte Debatte Orange Day)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture()
def vorgaenge() -> dict[str, dict[str, Any]]:
    return {str(v["id"]): v for v in load("vorgang")}


@pytest.fixture()
def positions() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for p in load("vorgangsposition"):
        out.setdefault(str(p["vorgang_id"]), []).append(p)
    return out
