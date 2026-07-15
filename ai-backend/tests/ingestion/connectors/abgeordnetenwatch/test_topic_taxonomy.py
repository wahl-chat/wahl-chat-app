# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for topic_taxonomy_config.py.

Test coverage:
  1. Resolution:
       - Known single-topic label → correct levels.
       - Verteidigung → [federal, state].
       - Unknown label → sorted(ALL_LEVELS) + logger.warning.
       - Empty topic list → sorted(ALL_LEVELS) + logger.warning.
  2. Coverage: all 53 AW Themen labels verified present in TOPIC_TAXONOMY.
"""

from __future__ import annotations

import logging

import pytest

import src.ingestion.connectors.abgeordnetenwatch.topic_taxonomy_config as ttc
from src.ingestion.connectors.abgeordnetenwatch.topic_taxonomy_config import (
    ALL_LEVELS,
    FEDERAL,
    MUNICIPAL,
    STATE,
    TOPIC_TAXONOMY,
    get_relevance_levels,
)


# ---------------------------------------------------------------------------
# 1. Resolution
# ---------------------------------------------------------------------------


def test_defense_returns_federal_and_state() -> None:
    """Verteidigung → [federal, state].

    A defense question in a Landtag election must surface Bundestag defense votes.
    """
    result = get_relevance_levels(["Verteidigung"])
    assert result == ["federal", "state"], (
        f"Verteidigung must map to ['federal', 'state'], got {result!r}"
    )


def test_federal_only_topic_returns_federal() -> None:
    """A federal-only topic must return only ['federal']."""
    result = get_relevance_levels(["Außenwirtschaft"])
    assert result == ["federal"], (
        f"Außenwirtschaft is federal-only, got {result!r}"
    )


def test_union_of_multiple_topics() -> None:
    """Union: Außenwirtschaft (federal) ∪ Verteidigung (federal, state) = [federal, state]."""
    result = get_relevance_levels(["Außenwirtschaft", "Verteidigung"])
    assert result == ["federal", "state"], (
        f"Union of federal ∪ (federal,state) must be ['federal', 'state'], got {result!r}"
    )


def test_unknown_label_returns_all_levels_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown AW Thema → sorted(ALL_LEVELS) + logger.warning (max recall).

    A new or misspelled topic label must never be silently buried —
    it falls back to ALL_LEVELS and emits a loud warning so the gap is visible.
    """
    unknown_label = "Unbekanntes Thema — nicht in der Taxonomie"
    with caplog.at_level(logging.WARNING, logger=ttc.logger.name):
        result = get_relevance_levels([unknown_label])

    assert result == sorted(ALL_LEVELS), (
        f"Unknown label must return sorted(ALL_LEVELS), got {result!r}"
    )
    assert any("not in TOPIC_TAXONOMY" in r.message for r in caplog.records), (
        "Unknown label must emit a logger.warning mentioning TOPIC_TAXONOMY"
    )


def test_empty_topic_list_returns_all_levels_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Empty topic list → sorted(ALL_LEVELS) + logger.warning (no-topic default).

    Polls without field_topics must not be silently buried — max-recall default.
    """
    with caplog.at_level(logging.WARNING, logger=ttc.logger.name):
        result = get_relevance_levels([])

    assert result == sorted(ALL_LEVELS), (
        f"Empty list must return sorted(ALL_LEVELS), got {result!r}"
    )
    assert any("no field_topics" in r.message for r in caplog.records), (
        "Empty topic list must emit a logger.warning"
    )


def test_result_is_always_sorted() -> None:
    """get_relevance_levels must return a sorted list regardless of input order."""
    result_forward = get_relevance_levels(["Verteidigung", "Außenwirtschaft"])
    result_reverse = get_relevance_levels(["Außenwirtschaft", "Verteidigung"])
    assert result_forward == result_reverse == sorted(result_forward), (
        "get_relevance_levels must always return a sorted list"
    )


def test_str_cast_on_untrusted_input() -> None:
    """Labels are cast to str before lookup (untrusted AW payload).

    Passing a non-string value that str()-ifies to an unknown label falls back to
    ALL_LEVELS.
    """
    result = get_relevance_levels([42])  # type: ignore[list-item]
    assert result == sorted(ALL_LEVELS), (
        "Non-string label should be cast to str, producing the ALL_LEVELS fallback"
    )


def test_soft_hyphen_in_label_still_resolves() -> None:
    """A topic label carrying an invisible soft hyphen (U+00AD) must normalize and match
    the taxonomy exactly — not silently fall back to ALL_LEVELS (which would make an
    affected federal vote over-surface in state chats)."""
    dirty = "Verteidi\u00adgung"  # U+00AD soft hyphen injected mid-word
    assert get_relevance_levels([dirty]) == ["federal", "state"], (
        "Soft-hyphen label must normalize to 'Verteidigung' and resolve to its levels"
    )


def test_reclassified_topics_include_state() -> None:
    """Kultur, Tourismus and Reaktorsicherheit are state-salient (Kulturhoheit /
    Länder execution) and must include STATE so they are not buried in Landtag chats."""
    for label in ("Kultur", "Tourismus", "Reaktorsicherheit"):
        assert get_relevance_levels([label]) == ["federal", "state"], (
            f"{label} must resolve to ['federal', 'state']"
        )


# ---------------------------------------------------------------------------
# 2. Coverage: all 53 AW Themen labels must be in TOPIC_TAXONOMY
# ---------------------------------------------------------------------------

# Exact label strings verified from the AW v2 /topics endpoint (2026-06-26).
_EXPECTED_53_LABELS: frozenset[str] = frozenset({
    "Verteidigung",
    "Außenpolitik und internationale Beziehungen",
    "Europapolitik und Europäische Union",
    "Außenwirtschaft",
    "Entwicklungspolitik",
    "Humanitäre Hilfe",
    "Menschenrechte",
    "Arbeit und Beschäftigung",
    "Soziale Sicherung",
    "Gesundheit",
    "Öffentliche Finanzen, Steuern und Abgaben",
    "Finanzen",
    "Haushalt",
    "Wirtschaft",
    "Energie",
    "Klima",
    "Umwelt",
    "Naturschutz",
    "Verkehr",
    "Bildung und Erziehung",
    "Raumordnung, Bau- und Wohnungswesen",
    "Landwirtschaft und Ernährung",
    "Migration und Aufenthaltsrecht",
    "Innere Sicherheit",
    "Innere Angelegenheiten",
    "Staat und Verwaltung",
    "Recht",
    "Gesellschaftspolitik, soziale Gruppen",
    "Familie",
    "Frauen",
    "Jugend",
    "Senioren",
    "Digitale Agenda",
    "digitale Infrastruktur",
    "Medien, Kommunikation und Informationstechnik",
    "Medien",
    "Kultur",
    "Sport",
    "Sport, Freizeit und Tourismus",
    "Tourismus",
    "Verbraucherschutz",
    "Forschung",
    "Wissenschaft, Forschung und Technologie",
    "Reaktorsicherheit",
    "Technologiefolgenabschätzung",
    "Lobbyismus & Transparenz",
    "Politisches Leben, Parteien",
    "Bundestag",
    "Geschäftsordnung",
    "Immunität",
    "Petitionen",
    "Wahlprüfung",
    "Deutsche Einheit / Innerdeutsche Beziehungen (bis 1990)",
})


def test_taxonomy_has_exactly_53_entries() -> None:
    """TOPIC_TAXONOMY must have exactly 53 entries."""
    assert len(TOPIC_TAXONOMY) == 53, (
        f"Expected 53 entries, got {len(TOPIC_TAXONOMY)}. "
        "Missing: {_EXPECTED_53_LABELS - set(TOPIC_TAXONOMY)}"
    )


def test_all_53_labels_are_present() -> None:
    """All 53 AW Themen labels must be present as exact-string keys."""
    taxonomy_keys = set(TOPIC_TAXONOMY.keys())
    missing = _EXPECTED_53_LABELS - taxonomy_keys
    extra = taxonomy_keys - _EXPECTED_53_LABELS
    assert not missing, (
        f"Labels missing from TOPIC_TAXONOMY: {missing!r}"
    )
    assert not extra, (
        f"Unexpected extra labels in TOPIC_TAXONOMY: {extra!r}"
    )


def test_all_taxonomy_values_are_subsets_of_all_levels() -> None:
    """Every TOPIC_TAXONOMY value must be a non-empty subset of ALL_LEVELS."""
    invalid = {
        label: levels
        for label, levels in TOPIC_TAXONOMY.items()
        if not levels or not levels.issubset(ALL_LEVELS)
    }
    assert not invalid, (
        f"TOPIC_TAXONOMY entries with invalid level sets: {invalid!r}"
    )


def test_all_levels_constant_matches_context_level_values() -> None:
    """ALL_LEVELS must equal {FEDERAL, STATE, MUNICIPAL} matching Context.level values."""
    assert ALL_LEVELS == {FEDERAL, STATE, MUNICIPAL}
    assert FEDERAL == "federal"
    assert STATE == "state"
    assert MUNICIPAL == "municipal"


# ---------------------------------------------------------------------------
# 3. Short-form embedded-label aliases (D2)
# ---------------------------------------------------------------------------


def test_short_form_oeffentliche_finanzen_resolves_like_long_form() -> None:
    """The embedded short form "Öffentliche Finanzen" must resolve to the same
    levels as the canonical "Öffentliche Finanzen, Steuern und Abgaben"."""
    short = get_relevance_levels(["Öffentliche Finanzen"])
    long = get_relevance_levels(["Öffentliche Finanzen, Steuern und Abgaben"])
    assert short == long == ["federal", "state"]


def test_all_aliases_match_their_canonical_levels() -> None:
    """Every _TOPIC_ALIASES value must be identical to a canonical key's levels."""
    for alias, levels in ttc._TOPIC_ALIASES.items():
        assert alias not in TOPIC_TAXONOMY, (
            f"Alias {alias!r} shadows a canonical TOPIC_TAXONOMY key"
        )
        assert levels in TOPIC_TAXONOMY.values(), (
            f"Alias {alias!r} levels {levels!r} do not match any canonical entry"
        )


def test_golden_fixture_labels_resolve_without_all_levels_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D2: every field_topics label in the golden poll fixtures must resolve via
    the taxonomy (canonical key or alias) WITHOUT the unknown-label ALL_LEVELS
    fallback — the fallback would make the vote over-surface in state/municipal
    chats and defeat the down-rank."""
    import json
    from pathlib import Path

    fixtures_dir = Path(__file__).parent / "fixtures"
    labels: list[str] = []
    for fixture in sorted(fixtures_dir.glob("aw_poll_*_poll.json")):
        poll = json.loads(fixture.read_text())["data"]
        labels.extend(
            str(t["label"])
            for t in (poll.get("field_topics") or [])
            if isinstance(t, dict) and t.get("label")
        )
    assert labels, "expected at least one field_topics label across golden fixtures"

    for label in labels:
        with caplog.at_level(logging.WARNING, logger=ttc.logger.name):
            caplog.clear()
            get_relevance_levels([label])
        assert not any(
            "not in TOPIC_TAXONOMY" in r.message for r in caplog.records
        ), f"Golden-fixture label {label!r} fell back to ALL_LEVELS (unmapped)"


# ---------------------------------------------------------------------------
# 4. Missing-topics warning gate (D14)
# ---------------------------------------------------------------------------


def test_empty_topics_warning_suppressed_for_non_federal(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """warn_on_missing_topics=False (non-federal legislatures) must NOT emit the
    per-poll no-field_topics WARNING; the ALL_LEVELS default still applies."""
    with caplog.at_level(logging.WARNING, logger=ttc.logger.name):
        result = get_relevance_levels([], warn_on_missing_topics=False)
    assert result == sorted(ALL_LEVELS)
    assert not any("no field_topics" in r.message for r in caplog.records), (
        "no-field_topics WARNING must be suppressed when warn_on_missing_topics=False"
    )


def test_unknown_label_still_warns_with_suppressed_missing_topics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unknown-label warnings stay loud everywhere — the D14 gate only covers
    the empty-input case."""
    with caplog.at_level(logging.WARNING, logger=ttc.logger.name):
        result = get_relevance_levels(
            ["Definitiv unbekanntes Thema"], warn_on_missing_topics=False
        )
    assert result == sorted(ALL_LEVELS)
    assert any("not in TOPIC_TAXONOMY" in r.message for r in caplog.records)
