# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from pathlib import Path

from ingestion.feed.items import content_hash, debate_item_id, split_digest
from ingestion.feed.models import DailyDigest

LEGACY_FIXTURE = Path(__file__).parent / "fixtures" / "legacy_daily_digests.json"


def _digests() -> list[DailyDigest]:
    return [
        DailyDigest.model_validate(d) for d in json.loads(LEGACY_FIXTURE.read_text())
    ]


def test_every_debate_and_vote_becomes_one_item_in_edition_order() -> None:
    for digest in _digests():
        edition, items = split_digest(digest)
        assert digest.session is not None
        assert len(items) == len(digest.session.sections) + len(digest.votes)
        assert edition.item_ids == [i.id for i in items]
        assert [i.rank for i in items] == list(range(len(items)))
        assert [i.kind for i in items] == ["debate"] * len(digest.session.sections) + [
            "vote"
        ] * len(digest.votes)


def test_ids_are_stable_and_survive_a_reordered_rebuild() -> None:
    digest = _digests()[0]
    assert digest.session is not None
    _, items = split_digest(digest)
    reordered = digest.model_copy(deep=True)
    assert reordered.session is not None
    reordered.session.sections.reverse()
    _, rebuilt = split_digest(reordered)
    assert {i.id for i in items} == {i.id for i in rebuilt}
    by_id = {i.id: i for i in rebuilt}
    for item in items:
        assert by_id[item.id].content["de"].headline == item.content["de"].headline


def test_ids_fit_the_feed_interest_rule_and_keep_legacy_keys() -> None:
    digest = _digests()[0]
    _, items = split_digest(digest)
    vote = next(i for i in items if i.kind == "vote")
    assert vote.id == f"{digest.id}_v{digest.votes[0].poll_id}"
    assert vote.legacy_keys == [f"{digest.id}~v{digest.votes[0].poll_id}"]
    debate = items[0]
    assert debate.legacy_keys == [f"{digest.id}~s0"]
    assert all(len(i.id) <= 120 for i in items)


def test_debate_id_ignores_agenda_order() -> None:
    assert debate_item_id("e", ["B", "A"]) == debate_item_id("e", ["A", "B"])
    assert debate_item_id("e", ["A"]) != debate_item_id("e", ["B"])


def test_texts_go_to_content_and_facts_stay_language_neutral() -> None:
    digest = _digests()[0]
    assert digest.session is not None
    section = digest.session.sections[0]
    _, items = split_digest(digest)
    debate = items[0]
    de = debate.content["de"]
    assert de.headline == section.headline
    assert de.teaser == section.summary
    assert [p.text for p in de.positions] == [p.position for p in section.positions]
    assert debate.debate is not None
    # Positions and their parties line up, so a locale never needs the facts copied.
    assert [p.party_id for p in debate.debate.parties] == [
        p.party_id for p in de.positions
    ]
    assert debate.debate.opening_quote == section.opening_quote
    assert de.source_hash == content_hash(de)


def test_duplicate_agenda_sets_do_not_overwrite_each_other() -> None:
    digest = _digests()[0]
    assert digest.session is not None
    twin = digest.session.sections[0].model_copy()
    digest.session.sections.append(twin)
    _, items = split_digest(digest)
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))


def test_a_debate_item_carries_both_topics_and_older_ones_their_single_topic() -> None:
    digest = _digests()[0]
    assert digest.session is not None
    first = digest.session.sections[0]
    assert first.topics == []  # stored before debates had two
    first.topics = [first.topic, "economy_finance"]
    _, items = split_digest(digest)
    assert items[0].topics == [first.topic, "economy_finance"]
    assert items[1].topics == [digest.session.sections[1].topic]
