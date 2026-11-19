# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ingestion.feed.builder import FeedBuilder
from ingestion.feed.models import FeedItem
from ingestion.feed.prompts import (
    TRANSLATION_PROMPT_VERSION,
    TranslatedSegment,
    TranslationBatch,
)
from ingestion.feed.translate import needs_translation, translate_items
from tests.feed.samples import sample_items

NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
_SEGMENT_RE = re.compile(r"^\[(S\d+)\] (.*)$", re.MULTILINE)

# (ref, German segment as sent) -> English text, or None to leave it out.
Edit = Callable[[str, str], Optional[str]]


def _items() -> list[FeedItem]:
    return sample_items()


class FakeTranslator:
    """Answers each segment with ``EN <segment>``, unless ``edit`` says otherwise."""

    def __init__(self, edit: Optional[Edit] = None, fail: bool = False) -> None:
        self.edit = edit
        self.fail = fail
        self.calls = 0

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        assert schema is TranslationBatch
        self.calls += 1
        if self.fail:
            raise RuntimeError("quota")
        segments = []
        for ref, german in _SEGMENT_RE.findall(messages[0].content):
            text = self.edit(ref, german) if self.edit else _english(german)
            if text is not None:
                segments.append(TranslatedSegment(ref=ref, text=text))
        return TranslationBatch(segments=segments), "fake-high"


def _english(german: str) -> str:
    # Quotes arrive in German marks and come back in English ones.
    if german.startswith("„") and german.endswith("“"):
        return f"“EN {german[1:-1]}”"
    return f"EN {german}"


def _run(items: list[FeedItem], **kwargs: Any) -> Any:
    fake = FakeTranslator(**kwargs)
    builder = FeedBuilder(fake)
    try:
        return translate_items(items, builder, now=NOW), fake
    finally:
        builder.close()


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_a_faithful_translation_is_published_with_its_provenance() -> None:
    items = _items()
    report, _ = _run(items)
    assert report.translated == len(items) and report.failed == 0
    for item in items:
        de, en = item.content["de"], item.content["en"]
        assert en.origin == "translated"
        assert en.headline == f"EN {_flat(de.headline)}"
        assert en.key_points == [f"EN {_flat(p)}" for p in de.key_points]
        assert en.source_hash == de.source_hash
        assert en.prompt_version == TRANSLATION_PROMPT_VERSION
        assert en.generated_by == "fake-high"
        assert [p.party_id for p in en.positions] == [p.party_id for p in de.positions]
        assert not needs_translation(item, "en")


def test_the_quote_is_translated_next_to_the_verbatim_original() -> None:
    items = _items()
    _run(items)
    item = next(i for i in items if i.debate and i.debate.opening_quote)
    assert item.debate is not None and item.debate.opening_quote is not None
    german = item.debate.opening_quote.text
    assert item.content["en"].quote_translation == f"EN {_flat(german)}"


def test_a_translation_that_loses_a_number_is_not_published() -> None:
    items = _items()
    target = next(
        i for i in items if any(c.isdigit() for c in (i.content["de"].teaser or ""))
    )
    teaser = _flat(target.content["de"].teaser or "")

    def drop_digits(ref: str, german: str) -> str:
        return "EN no numbers here" if german == teaser else _english(german)

    report, _ = _run(items, edit=drop_digits)
    assert "en" not in target.content
    assert report.failed == 1


def test_a_translation_that_drops_a_party_is_not_published() -> None:
    items = _items()
    target = next(i for i in items if len(i.content["de"].positions) > 1)
    position = _flat(target.content["de"].positions[0].text)

    def drop_party(ref: str, german: str) -> Optional[str]:
        return None if german == position else _english(german)

    _run(items, edit=drop_party)
    assert "en" not in target.content


def test_runaway_output_is_not_published() -> None:
    items = _items()
    headline = _flat(items[0].content["de"].headline)

    def run_on(ref: str, german: str) -> str:
        if german == headline:
            return "EN headline\n\nTranslated with DeepL.com (free version)\n\n\n"
        return _english(german)

    _run(items, edit=run_on)
    assert "en" not in items[0].content
    assert all("en" in i.content for i in items[1:])


def test_refs_never_leak_into_translated_text() -> None:
    items = _items()
    _run(items, edit=lambda ref, german: f"{_english(german)} ({ref})")
    assert all("(S" not in i.content["en"].headline for i in items)


def test_a_stale_translation_is_dropped_when_retranslation_fails() -> None:
    items = _items()
    _run(items)
    item = items[0]
    item.content["de"].source_hash = "changed"
    assert needs_translation(item, "en")
    report, _ = _run(items, fail=True)
    assert "en" not in item.content
    assert report.dropped_stale == 1


def test_current_translations_cost_no_call() -> None:
    items = _items()
    _run(items)
    _, fake = _run(items)
    assert fake.calls == 0


def test_retracted_items_are_not_translated() -> None:
    items = [i.model_copy(update={"status": "retracted"}) for i in _items()]
    _, fake = _run(items)
    assert fake.calls == 0
