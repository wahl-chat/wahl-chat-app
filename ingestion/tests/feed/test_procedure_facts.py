# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The feed run attaches procedure summaries as source facts."""

from datetime import date

from ingestion.feed.builder import plan_days
from ingestion.feed.bulk import attach_source_facts
from ingestion.feed.parliaments import PARLIAMENTS
from wahlchat_common.procedures import ProcedureSummary

from .samples import sample_items, sittings, vote

SUMMARY = ProcedureSummary(
    vorgang_id="338366", titel="Haushaltsbegleitgesetz 2027", vorgangstyp="Gesetzgebung",
    kind="legislation", latest_stage="1. Beratung", latest_stage_on=date(2026, 9, 8),
    dip_url="https://dip.bundestag.de/vorgang/338366",
)


def _plan():
    [plan, *_] = plan_days(PARLIAMENTS["bundestag"], [vote(1), vote(2)], sittings())
    return plan


def test_items_get_procedure_ids_and_summaries() -> None:
    seen: list[tuple[str, int]] = []

    def facts(item, speech_links):  # noqa: ANN001, ANN202
        seen.append((item.id, len(speech_links)))
        return ["338366"], [SUMMARY]

    items, changed = attach_source_facts(sample_items(), _plan(), None, facts)
    assert all(i.procedure_ids == ["338366"] and i.procedures == [SUMMARY] for i in items)
    assert changed == {i.id for i in items}
    # a debate hands its speeches' links over; a vote has none
    assert any(n > 0 for _, n in seen)


def test_unchanged_procedures_do_not_mark_items_changed() -> None:
    items, _ = attach_source_facts(sample_items(), _plan(), None, lambda i, s: (["338366"], [SUMMARY]))
    _, changed = attach_source_facts(items, _plan(), None, lambda i, s: (["338366"], [SUMMARY]))
    assert changed == set()


def test_without_a_lookup_items_stay_as_they_are() -> None:
    items, _ = attach_source_facts(sample_items(), _plan(), None)
    assert all(i.procedure_ids == [] for i in items)
