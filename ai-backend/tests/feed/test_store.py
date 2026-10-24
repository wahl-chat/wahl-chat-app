# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from pathlib import Path

from src.feed.items import split_digest
from src.feed.models import DailyDigest, FeedItem, LocalizedContent
from src.feed.prompts import TRANSLATION_PROMPT_VERSION
from src.feed.store import carry_over_translations, vanished_items

LEGACY_FIXTURE = Path(__file__).parent / "fixtures" / "legacy_daily_digests.json"


def _digest() -> DailyDigest:
    return DailyDigest.model_validate(json.loads(LEGACY_FIXTURE.read_text())[0])


def _with_english(item: FeedItem) -> FeedItem:
    de = item.content["de"]
    item.content["en"] = LocalizedContent(
        headline="EN",
        origin="translated",
        source_hash=de.source_hash,
        prompt_version=TRANSLATION_PROMPT_VERSION,
        generated_at=de.generated_at,
    )
    return item


def test_a_debate_dropped_from_a_rebuilt_day_is_retracted_not_deleted() -> None:
    digest = _digest()
    old_edition, old_items = split_digest(digest)
    assert digest.session is not None
    rebuilt = digest.model_copy(deep=True)
    assert rebuilt.session is not None
    rebuilt.session.sections.pop(0)
    new_edition, _ = split_digest(rebuilt)

    stored = {i.id: i for i in old_items}
    [gone] = vanished_items({old_edition.id: old_edition}, [new_edition], stored)
    assert gone.id == old_items[0].id
    assert gone.status == "retracted"
    assert stored[gone.id].status == "published"  # the stored copy is untouched


def test_unchanged_texts_keep_their_translation_across_a_rebuild() -> None:
    _, old_items = split_digest(_digest())
    stored = {i.id: _with_english(i.model_copy(deep=True)) for i in old_items}
    _, items = split_digest(_digest())
    items[0].content["de"].source_hash = "regenerated differently"

    kept = carry_over_translations(items, stored)
    assert kept == len(items) - 1
    assert "en" not in items[0].content
    assert all("en" in i.content for i in items[1:])
