# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

import pytest

from ingestion.feed import items as items_module
from ingestion.feed.items import (
    MAX_POSITION_ATTEMPTS,
    assemble_edition,
    build_needed,
    content_hash,
    debate_item_id,
    vote_input_hash,
    vote_item_id,
)
from tests.feed.samples import BUNDESTAG, NOW, sample_items


def test_ids_come_from_the_source_and_fit_the_feed_interest_rule() -> None:
    assert debate_item_id("bundestag_2026-09-24", 45, "zp3") == (
        "bundestag_2026-09-24_d45-zp3"
    )
    assert vote_item_id("bundestag_2026-09-24", 6201) == "bundestag_2026-09-24_v6201"
    assert all(len(i.id) <= 120 for i in sample_items())


def test_a_rebuilt_item_keeps_its_id() -> None:
    assert [i.id for i in sample_items()] == [i.id for i in sample_items()]


def test_the_vote_hash_follows_its_source() -> None:
    payload = {"content_hash": "a"}
    assert vote_input_hash(payload) == vote_input_hash({"content_hash": "a"})
    assert vote_input_hash(payload) != vote_input_hash({"content_hash": "b"})


def test_what_a_stored_item_needs_follows_its_hash_and_pending_positions() -> None:
    item = sample_items()[0].model_copy(update={"input_hash": "h"})
    assert build_needed(None, "h") == "full"
    assert build_needed(item, "other") == "full"
    assert build_needed(item.model_copy(update={"status": "retracted"}), "h") == "full"
    assert build_needed(item, "h") is None
    pending = item.model_copy(
        update={"pending_positions": ["cdu"], "position_attempts": 1}
    )
    assert build_needed(pending, "h") == "positions"
    exhausted = pending.model_copy(update={"position_attempts": MAX_POSITION_ATTEMPTS})
    assert build_needed(exhausted, "h") is None


def test_the_edition_lists_items_in_order_and_ranks_them() -> None:
    items = sample_items()
    reversed_items = list(reversed(items))
    edition, ranked = assemble_edition(
        BUNDESTAG, "bundestag_2026-09-24", date(2026, 9, 24), [], reversed_items, NOW
    )
    assert edition.item_ids == [i.id for i in reversed_items]
    assert [i.rank for i in ranked] == list(range(len(items)))
    # The given items are not mutated; re-ranked ones are copies.
    assert [i.rank for i in reversed_items] == [0] * len(items)


def test_texts_go_to_content_and_facts_stay_language_neutral() -> None:
    debate = sample_items()[0]
    de = debate.content["de"]
    assert de.headline == "Debatte: Wohnungsbau"
    assert de.source_hash == content_hash(de)
    assert debate.debate is not None
    assert debate.debate.agenda_item == "Wohnungsbau"
    assert [p.protocol_id for p in debate.debate.protocols] == ["21/45"]
    # Positions follow the order of the parties in the facts.
    facts_order = [p.party_id for p in debate.debate.parties]
    assert [p.party_id for p in de.positions] == [
        p for p in facts_order if p in {q.party_id for q in de.positions}
    ]


def test_the_hash_covers_the_sources_not_the_prompt_or_format_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = vote_input_hash({"content_hash": "a"})
    monkeypatch.setattr(items_module, "PROMPT_VERSION", "99")
    assert vote_input_hash({"content_hash": "a"}) == before


def test_an_item_stored_under_the_old_hash_counts_as_current() -> None:
    payload = {"content_hash": "a"}
    item = sample_items()[0].model_copy(
        update={"input_hash": vote_input_hash(payload, legacy=True)}
    )
    current = vote_input_hash(payload)
    legacy = vote_input_hash(payload, legacy=True)
    assert current != legacy
    assert build_needed(item, current, legacy) is None
    # Without the legacy hash to compare, the old item would be rebuilt.
    assert build_needed(item, current) == "full"


def test_a_source_change_rebuilds_an_item_stored_under_the_old_hash() -> None:
    item = sample_items()[0].model_copy(
        update={"input_hash": vote_input_hash({"content_hash": "a"}, legacy=True)}
    )
    changed = {"content_hash": "b"}
    assert (
        build_needed(
            item, vote_input_hash(changed), vote_input_hash(changed, legacy=True)
        )
        == "full"
    )


def test_a_vote_whose_texts_fell_back_is_always_retried() -> None:
    item = sample_items()[0].model_copy(update={"input_hash": None})
    assert build_needed(item, "h", "legacy") == "full"
