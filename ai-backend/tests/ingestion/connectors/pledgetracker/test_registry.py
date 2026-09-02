# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pledge registry unit tests (JSONL loader, region mapping, party resolution, ids).

Tests defined here:
  - test_loads_committed_sample_registry: the committed sample parses; region codes
    are ISO 3166-2 (DE-ST) so they match context region_path elements.
  - test_region_codes_are_iso_3166_2: every Bundesland maps to a DE-XX code.
  - test_party_slug_reuses_shared_tables: canonical + state tables resolve labels,
    including labels with a trailing Bundesland ("CDU Sachsen-Anhalt").
  - test_party_slug_quarantines_unknown_labels: unknown parties → 'unbekannt'
    (framework convention), never a crash.
  - test_explicit_party_id_override_wins: coalition rows pin the lead party.
  - test_pledge_id_is_deterministic: same input → same id across instances.
  - test_malformed_registry_lines_are_skipped: bad rows warn-and-skip.
"""

from __future__ import annotations

from pathlib import Path

from src.ingestion.connectors.pledgetracker.registry import (
    BUNDESLAND_TO_REGION,
    PledgeInput,
    load_pledge_registry,
    party_slug,
)
from src.ingestion.ids import compute_source_item_id
from src.ingestion.party_slugs import PARTY_SLUG_QUARANTINE
from src.ingestion.schemas import SourceType

_AI_BACKEND = Path(__file__).resolve().parents[4]
_SAMPLE_REGISTRY = _AI_BACKEND / "data/pledges/sample_pledges.jsonl"


def _cdu_input() -> PledgeInput:
    return PledgeInput(
        claim="Wir wollen, dass die A14 fertig wird",
        pledge_date="2021-03-27",
        pledge_author="CDU",
        bundesland="Sachsen-Anhalt",
    )


def test_loads_committed_sample_registry() -> None:
    """The committed sample parses; ISO region codes match context region_paths."""
    inputs = load_pledge_registry(_SAMPLE_REGISTRY)
    assert len(inputs) == 2

    cdu, spd = inputs
    assert cdu.resolved_party_id() == "cdu"
    assert cdu.region == "DE-ST"
    assert cdu.region_path == ["DE", "DE-ST"]
    assert cdu.job_inputs()["bundesland"] == "Sachsen-Anhalt"
    assert cdu.job_inputs()["time_range"] == "since_pledge_date"

    # The SPD row pins its pledge_id so re-ingestion upserts the same doc.
    assert spd.resolved_pledge_id() == "spd-mindestlohn-12-euro-de-2021"
    assert spd.region == "DE"
    assert spd.region_path == ["DE"]
    assert "bundesland" not in spd.job_inputs()


def test_region_codes_are_iso_3166_2() -> None:
    """All 16 Bundesländer map to DE-XX codes (match the context seeds)."""
    assert len(BUNDESLAND_TO_REGION) == 16
    assert BUNDESLAND_TO_REGION["sachsen-anhalt"] == "DE-ST"
    assert BUNDESLAND_TO_REGION["bayern"] == "DE-BY"
    assert all(code.startswith("DE-") for code in BUNDESLAND_TO_REGION.values())


def test_party_slug_reuses_shared_tables() -> None:
    """Labels resolve via party_slugs.py, incl. trailing-Bundesland stripping."""
    assert party_slug("CDU") == "cdu"
    assert party_slug("CDU Sachsen-Anhalt") == "cdu"
    assert party_slug("BÜNDNIS 90/DIE GRÜNEN") == "gruene"
    assert party_slug("Freie Wähler") == "fw"
    assert party_slug("DIE LINKE Sachsen-Anhalt") == "linke"


def test_party_slug_quarantines_unknown_labels() -> None:
    """Unknown parties quarantine to 'unbekannt' (framework convention)."""
    assert party_slug("Zentrumspartei") == PARTY_SLUG_QUARANTINE


def test_explicit_party_id_override_wins() -> None:
    """Coalition rows pin the lead party explicitly."""
    pledge = PledgeInput(
        claim="Wir bauen aus.",
        pledge_date="2021-09-13",
        pledge_author="CDU Sachsen-Anhalt, SPD Sachsen-Anhalt, FDP Sachsen-Anhalt",
        party_id="cdu",
    )
    assert pledge.resolved_party_id() == "cdu"


def test_pledge_id_is_deterministic() -> None:
    """Same pledge input → same id across instances (re-runs upsert in place)."""
    pledge = _cdu_input()
    expected = str(
        compute_source_item_id(
            SourceType.PLEDGE_RECORD.value,
            f"cdu:{pledge.claim}:DE-ST",
        )
    )
    assert pledge.resolved_pledge_id() == expected
    assert _cdu_input().resolved_pledge_id() == expected


def test_malformed_registry_lines_are_skipped(tmp_path: Path) -> None:
    """Bad JSONL rows are warn-and-skip; the good rows still load."""
    registry = tmp_path / "pledges.jsonl"
    registry.write_text(
        '{"claim": "ok", "pledge_date": "2021-01-01", "pledge_author": "SPD"}\n'
        "not json at all\n"
        '{"pledge_date": "2021-01-01"}\n',
        encoding="utf-8",
    )
    inputs = load_pledge_registry(registry)
    assert len(inputs) == 1
    assert inputs[0].claim == "ok"
