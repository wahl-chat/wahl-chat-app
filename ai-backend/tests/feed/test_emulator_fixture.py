# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from pathlib import Path

from src.feed.models import FeedEdition, FeedItem
from src.feed.translate import needs_translation

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "firebase"
    / "firestore_data"
    / "emulator"
    / "feed.json"
)


def test_emulator_sample_feed_matches_the_stored_shape() -> None:
    # `make seed-local` writes this into the emulator for the feed; it must
    # stay what the builder would write, or local review shows a fake feed.
    feed = json.loads(FIXTURE.read_text())
    editions = [FeedEdition.model_validate(e) for e in feed["editions"]]
    items = {i["id"]: FeedItem.model_validate(i) for i in feed["items"]}
    assert editions
    for edition in editions:
        assert edition.item_ids
        assert all(item_id in items for item_id in edition.item_ids)
    for item in items.values():
        # Local review covers both languages.
        assert not needs_translation(item, "en")
        if item.debate is not None:
            assert item.debate.opening_quote is not None
