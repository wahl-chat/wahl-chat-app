# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared text-normalisation utilities for the bundestag_speeches connector.

Public API:
  normalize_whitespace(text) -> str | None
  normalize_name_for_lookup(text) -> str
  normalize_party(value) -> str | None   (alias resolution via PARTY_ALIASES)
  is_known_party(value) -> bool
  parse_int(value) -> int
"""

from __future__ import annotations

import re

from .constants import PARTY_ALIASES, VALID_PARTIES


def normalize_whitespace(text: str | None) -> str | None:
    if text is None:
        return None
    return re.sub(r"\s+", " ", text).strip()


def normalize_name_for_lookup(text: str | None) -> str:
    text = normalize_whitespace(text) or ""
    text = text.replace(" ", " ")
    text = re.sub(r"\b(Dr|Prof)\.\s*", "", text)
    text = re.sub(r"\([^)]*\)", "", text)
    return re.sub(r"[^a-zäöüß ]", "", text.lower()).strip()


def normalize_party(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None

    key = value.replace(" ", " ")
    key = re.sub(r"\s+", " ", key).strip().upper()
    return PARTY_ALIASES.get(key, value)


def is_known_party(value: str | None) -> bool:
    return normalize_party(value) in VALID_PARTIES


def parse_int(value: str | None) -> int:
    try:
        return int(normalize_whitespace(value) or 0)
    except ValueError:
        return 0
