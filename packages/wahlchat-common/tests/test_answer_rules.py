# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Shared answer rules: language instruction and domain lists."""

from __future__ import annotations

import pytest

from wahlchat_common.answer_rules import (
    CIVIC_DOMAINS,
    LANGUAGE_NAMES,
    PREFERRED_OUTLETS,
    language_rule,
)


@pytest.mark.parametrize("language,name", [("de", "German"), ("en", "English")])
def test_language_rule_names_the_fallback_language(language: str, name: str) -> None:
    rule = language_rule(language)  # type: ignore[arg-type]
    assert f"answer in {name}" in rule
    assert "language of the user's last message" in rule


def test_language_names_cover_every_language() -> None:
    assert set(LANGUAGE_NAMES) == {"de", "en"}


@pytest.mark.parametrize("domains", [PREFERRED_OUTLETS, CIVIC_DOMAINS])
def test_domain_lists_are_bare_unique_hosts(domains: tuple[str, ...]) -> None:
    # Longer lists than a search_domain_filter takes are split by the caller.
    assert len(domains) > 0
    assert len(set(domains)) == len(domains)
    assert all(d == d.lower() and "/" not in d and not d.startswith("www.") for d in domains)
