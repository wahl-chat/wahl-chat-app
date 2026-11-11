# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import gzip
import json
from pathlib import Path

from ingestion.feed.models import FeedEdition, FeedItem, SittingCalendar
from ingestion.feed.politicians import Politician, speaker_ids
from ingestion.feed.translate import needs_translation

EMULATOR_DATA = (
    Path(__file__).resolve().parents[3] / "firebase" / "firestore_data" / "emulator"
)
FIXTURE = EMULATOR_DATA / "feed.json"
POLITICIANS = EMULATOR_DATA / "politicians.json.gz"


def test_emulator_sample_feed_matches_the_stored_shape() -> None:
    # `make seed-local` writes this into the emulator for the feed; it must
    # stay what the builder would write, or local review shows a fake feed.
    feed = json.loads(FIXTURE.read_text())
    editions = [FeedEdition.model_validate(e) for e in feed["editions"]]
    items = {i["id"]: FeedItem.model_validate(i) for i in feed["items"]}
    assert SittingCalendar.model_validate(feed["calendar"]).weeks
    assert editions
    for edition in editions:
        assert edition.item_ids
        assert all(item_id in items for item_id in edition.item_ids)
    for item in items.values():
        # Local review covers both languages.
        assert not needs_translation(item, "en")
        if item.debate is not None:
            assert item.debate.opening_quote is not None


def test_emulator_politicians_match_the_stored_shape_and_the_speakers() -> None:
    # The card a speaker opens in local review reads these.
    politicians = {
        record.mdb_id: record
        for record in (
            Politician.model_validate(p)
            for p in json.loads(gzip.decompress(POLITICIANS.read_bytes()))
        )
    }
    items = [
        FeedItem.model_validate(i) for i in json.loads(FIXTURE.read_text())["items"]
    ]
    ids = speaker_ids(items)
    assert ids
    # Every identified speaker who is a member has a record.
    members = [i for i in ids if not i.startswith("9999")]
    assert set(members) <= set(politicians)
