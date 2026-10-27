# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
import re
from pathlib import Path
from typing import Any, Callable, Optional

from ingestion.feed.builder import DigestBuilder
from ingestion.feed.prompts import TranslatedSegment, TranslationBatch
from ingestion.i18n_catalog.translate_messages import (
    flatten,
    message_problems,
    read_catalog,
    read_sources,
    run,
    unflatten,
)

GERMAN = {
    "nav": {"donate": "Spenden", "toElection": "Zur {name}"},
    "chat": {
        "parties": "{count, plural, one {# Partei} other {# Parteien}}",
        "terms": "Mit dem Absenden stimmst du den <link>Nutzungsbedingungen</link> zu.",
    },
    "empty": {},
}
FRENCH = {
    "Spenden": "Faire un don",
    "Zur {name}": "Vers {name}",
    "{count, plural, one {# Partei} other {# Parteien}}": "{count, plural, one {# parti} other {# partis}}",
    "Mit dem Absenden stimmst du den <link>Nutzungsbedingungen</link> zu.": "En envoyant, tu acceptes les <link>conditions</link>.",
}
_SEGMENT_RE = re.compile(r"^\[(S\d+)\] (.*)$", re.MULTILINE)


def _write(tmp_path: Path, locale: str, tree: dict) -> None:
    directory = tmp_path / locale
    directory.mkdir(parents=True, exist_ok=True)
    for namespace, content in tree.items():
        (directory / f"{namespace}.json").write_text(json.dumps(content))


class FakeModel:
    def __init__(self, edit: Optional[Callable[[str], str]] = None) -> None:
        self.edit = edit
        self.calls = 0

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        assert schema is TranslationBatch
        self.calls += 1
        segments = []
        for ref, german in _SEGMENT_RE.findall(messages[0].content):
            text = FRENCH[german]
            segments.append(
                TranslatedSegment(ref=ref, text=self.edit(text) if self.edit else text)
            )
        return TranslationBatch(segments=segments), "fake"


def _run(tmp_path: Path, model: FakeModel, **kwargs: Any) -> Any:
    builder = DigestBuilder(model)
    try:
        return run("fr", tmp_path, builder=builder, **kwargs)
    finally:
        builder.close()


def test_flatten_and_unflatten_round_trip() -> None:
    assert unflatten(flatten(GERMAN["chat"])) == GERMAN["chat"]
    assert flatten({"seat": {"yes": "Ja"}}) == {"seat.yes": "Ja"}


def test_a_new_language_is_filled_completely(tmp_path: Path) -> None:
    _write(tmp_path, "de", GERMAN)
    report = _run(tmp_path, FakeModel())
    assert not report.failed
    french = read_catalog(tmp_path / "fr")
    assert french["nav.donate"] == "Faire un don"
    assert french["chat.parties"].startswith("{count, plural")
    # Empty namespaces get a file too: the locale's index imports every one.
    assert json.loads((tmp_path / "fr" / "empty.json").read_text()) == {}
    assert set(read_sources(tmp_path, "fr")) == set(flatten(GERMAN))


def test_only_changed_german_messages_are_translated_again(tmp_path: Path) -> None:
    _write(tmp_path, "de", GERMAN)
    _run(tmp_path, FakeModel())
    idle = FakeModel()
    assert _run(tmp_path, idle).pending == []
    assert idle.calls == 0

    changed = json.loads(json.dumps(GERMAN))
    changed["nav"]["donate"] = "Spenden"  # unchanged
    changed["nav"]["toElection"] = "Zur {name}"
    _write(tmp_path, "de", changed)
    sources = read_sources(tmp_path, "fr")
    sources["nav.toElection"] = "stale"
    (tmp_path / ".sources" / "fr.json").write_text(json.dumps(sources))
    assert _run(tmp_path, FakeModel()).pending == ["nav.toElection"]


def test_hand_written_translations_are_adopted_not_overwritten(
    tmp_path: Path,
) -> None:
    _write(tmp_path, "de", GERMAN)
    _write(tmp_path, "fr", {"nav": {"donate": "Don (à la main)"}})
    run("fr", tmp_path, builder=None, adopt=True)
    report = _run(tmp_path, FakeModel())
    assert "nav.donate" not in report.pending
    assert read_catalog(tmp_path / "fr")["nav.donate"] == "Don (à la main)"


def test_broken_translations_are_reported_not_written(tmp_path: Path) -> None:
    _write(tmp_path, "de", GERMAN)
    report = _run(tmp_path, FakeModel(edit=lambda t: t.replace("{name}", "{nom}")))
    assert "nav.toElection" in report.failed
    assert "nav.toElection" not in read_catalog(tmp_path / "fr")
    assert "nav.toElection" not in read_sources(tmp_path, "fr")


def test_checks_catch_lost_placeholders_branches_tags_and_runaways() -> None:
    assert message_problems("Zur {name}", "To {name}") == []
    assert message_problems("Zur {name}", "To the election")
    plural = "{count, plural, one {# Partei} other {# Parteien}}"
    assert message_problems(plural, "{count, plural, other {# parties}}")
    assert message_problems("Die <link>AGB</link>", "The terms")
    assert message_problems("Teilen", "Share\n\nTranslated with DeepL.com")
    assert message_problems("Teilen", "") == ["empty"]
