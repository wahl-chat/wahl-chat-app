# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from ingestion.feed.items import (
    assemble_edition,
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
