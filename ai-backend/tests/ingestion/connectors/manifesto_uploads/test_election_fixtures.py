# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for election_fixtures.py — the gate that keeps chunks retrievable.

The two fields these tests protect (``region``, ``party_id``) decide whether a
chunk is ever returned by a filtered query, and a wrong value produces NO error at
ingest time. Every failure mode is therefore asserted to RAISE rather than default.

Also pins the real repo fixtures for the Sachsen-Anhalt election, so a later edit
to contexts.json that drops region_path or level fails here instead of silently
making that election's manifestos unreachable.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.ingestion.connectors.manifesto_uploads import election_fixtures
from src.ingestion.connectors.manifesto_uploads.election_fixtures import (
    FixtureLookupError,
    load_election,
    require_party,
)

_CTX = "landtagswahl-testland-2026"


def _write_fixtures(
    tmp_path: Path,
    *,
    context: dict | None = None,
    parties: dict | None = None,
    write_parties: bool = True,
) -> Path:
    """Write a minimal seed-data dir and return its env directory."""
    env_dir = tmp_path / "firebase" / "firestore_data" / "dev"
    env_dir.mkdir(parents=True)
    ctx = {
        "context_id": _CTX,
        "name": "Landtagswahl Testland 2026",
        "date": "2026-09-06",
        "region_path": ["DE", "DE-TL"],
        "level": "state",
    }
    if context is not None:
        ctx.update(context)
        ctx = {k: v for k, v in ctx.items() if v is not _DROP}
    (env_dir / "contexts.json").write_text(json.dumps({_CTX: ctx}), encoding="utf-8")
    if write_parties:
        (env_dir / f"parties_{_CTX}.json").write_text(
            json.dumps(parties if parties is not None else {"spd": {}, "cdu": {}}),
            encoding="utf-8",
        )
    return env_dir


class _Drop:
    """Sentinel marking a key that must be ABSENT from the written fixture."""


_DROP = _Drop()


@pytest.fixture(autouse=True)
def _isolate_fixture_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Point fixture_dir at a temp tree and clear the lru_caches around each test."""
    election_fixtures._contexts.cache_clear()
    election_fixtures._parties.cache_clear()
    yield
    election_fixtures._contexts.cache_clear()
    election_fixtures._parties.cache_clear()


def _patch_dir(monkeypatch: pytest.MonkeyPatch, env_dir: Path) -> None:
    monkeypatch.setattr(election_fixtures, "fixture_dir", lambda env=None: env_dir)
    election_fixtures._contexts.cache_clear()
    election_fixtures._parties.cache_clear()


# ===========================================================================
# Happy path
# ===========================================================================


def test_loads_region_level_date_and_parties(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path))
    fixture = load_election(_CTX)
    # The MOST SPECIFIC region — manifesto retrieval matches on region_path[-1].
    assert fixture.region == "DE-TL"
    assert fixture.level == "state"
    assert fixture.election_date == date(2026, 9, 6)
    assert fixture.party_ids == frozenset({"spd", "cdu"})
    assert fixture.name == "Landtagswahl Testland 2026"


def test_federal_context_resolves_to_de(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(
        monkeypatch,
        _write_fixtures(tmp_path, context={"region_path": ["DE"], "level": "federal"}),
    )
    assert load_election(_CTX).region == "DE"


def test_municipal_region_is_the_deepest_element(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(
        monkeypatch,
        _write_fixtures(
            tmp_path,
            context={"region_path": ["DE", "DE-BY", "DE-BY-MUC"], "level": "municipal"},
        ),
    )
    assert load_election(_CTX).region == "DE-BY-MUC"


# ===========================================================================
# Every silent-failure mode raises instead
# ===========================================================================


def test_unknown_election_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path))
    with pytest.raises(FixtureLookupError, match="unknown election"):
        load_election("landtagswahl-nowhere-2026")


def test_missing_region_path_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The dangerous default: Context falls back to ["DE"], which would scope a
    # state election's manifestos to federal and hide them.
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, context={"region_path": _DROP}))
    with pytest.raises(FixtureLookupError, match="no region_path"):
        load_election(_CTX)


def test_empty_region_path_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, context={"region_path": []}))
    with pytest.raises(FixtureLookupError, match="no region_path"):
        load_election(_CTX)


@pytest.mark.parametrize("level", [_DROP, None, "", "regional", "Bundesland"])
def test_missing_or_unknown_level_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, level: object
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, context={"level": level}))
    with pytest.raises(FixtureLookupError, match="level"):
        load_election(_CTX)


def test_missing_date_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, context={"date": _DROP}))
    with pytest.raises(FixtureLookupError, match="no date"):
        load_election(_CTX)


def test_unparseable_date_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, context={"date": "06.09.2026"}))
    with pytest.raises(FixtureLookupError, match="unparseable date"):
        load_election(_CTX)


def test_missing_party_file_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, write_parties=False))
    with pytest.raises(FixtureLookupError, match="seed file not found"):
        load_election(_CTX)


def test_empty_party_file_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_dir(monkeypatch, _write_fixtures(tmp_path, parties={}))
    with pytest.raises(FixtureLookupError, match="declares no parties"):
        load_election(_CTX)


# ===========================================================================
# require_party — the tenant key must match exactly
# ===========================================================================


class TestRequireParty:
    """A near-miss slug is rejected, with the correct spelling suggested."""

    @pytest.fixture()
    def fixture(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _patch_dir(monkeypatch, _write_fixtures(tmp_path))
        return load_election(_CTX)

    def test_exact_match_passes_through(self, fixture) -> None:
        assert require_party(fixture, "spd") == "spd"

    def test_wrong_case_is_rejected_with_a_hint(self, fixture) -> None:
        # "SPD" would be written successfully and then never retrieved, because
        # party_id is the tenant key and the filter is an exact MatchValue.
        with pytest.raises(FixtureLookupError, match="did you mean 'spd'"):
            require_party(fixture, "SPD")

    def test_unknown_party_is_rejected(self, fixture) -> None:
        with pytest.raises(FixtureLookupError, match="not configured for election"):
            require_party(fixture, "spd-testland")


# ===========================================================================
# The real repo fixtures for Sachsen-Anhalt
# ===========================================================================


def test_real_sachsen_anhalt_fixtures_are_ingestable() -> None:
    """The shipped dev fixtures resolve, with the region retrieval expects."""
    fixture = load_election("landtagswahl-sachsen-anhalt-2026", env="dev")
    assert fixture.region == "DE-ST"
    assert fixture.level == "state"
    assert fixture.election_date == date(2026, 9, 6)
    # Every party whose programme is in the manifest must be configured.
    assert {
        "spd",
        "cdu",
        "afd",
        "gruene",
        "linke",
        "fdp",
        "bsw",
        "fw",
        "basis",
        "tierschutzpartei",
        "pdf",
        "gartenpartei",
    } <= fixture.party_ids
