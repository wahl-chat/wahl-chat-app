# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Fill a language's UI catalogs from the German ones.

German (``web/messages/de/*.json``) is the source. For a target locale, only
messages that are missing or whose German text changed since they were
translated go to the model; the German hash each translation was made from is
kept in ``web/messages/.sources/{locale}.json``. A translation is written only
when it keeps every ICU placeholder, plural/select branch and rich-text tag of
its German message; anything else is reported and left for the next run.

Usage:
    make translate-messages LOCALE=fr
    uv run python -m ingestion.i18n_catalog.translate_messages --locale fr --dry-run
    # Record hand-written translations as current, without any LLM call:
    uv run python -m ingestion.i18n_catalog.translate_messages --locale en --adopt
"""

from __future__ import annotations

# Load the env file before the imports below (the LLM roster reads its keys
# and Vertex settings from the environment). override=False keeps exported
# variables in force.
if __name__ == "__main__":
    from pathlib import Path as _Path

    from dotenv import load_dotenv

    _env_path = _Path(__file__).resolve().parents[3] / ".env"
    # Use ai-backend/.env when ingestion/.env does not exist.
    if not _env_path.exists():
        _env_path = _env_path.parents[1] / "ai-backend" / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

import hashlib
import json
import logging
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ingestion.feed.builder import DigestBuilder, strip_refs
from ingestion.feed.prompts import TranslationBatch
from ingestion.i18n_catalog.prompts import CATALOG_PROMPT_VERSION, format_catalog_prompt

logger = logging.getLogger(__name__)

SOURCE_LOCALE = "de"
DEFAULT_MESSAGES_DIR = Path(__file__).resolve().parents[4] / "web" / "messages"
_BATCH = 40

_ARGUMENT_RE = re.compile(r"\{\s*([A-Za-z_]\w*)\s*[,}]")
_BRANCH_RE = re.compile(r"(?<![\w=])(zero|one|two|few|many|other|=\d+)\s*\{")
_TAG_RE = re.compile(r"</?([A-Za-z][\w-]*)>")
_RUNAWAY_RE = re.compile(r"deepl|translated with|\n\s*\n\s*\n", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Catalog files
# ---------------------------------------------------------------------------


def flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """``{"seat": {"yes": "Ja"}}`` → ``{"seat.yes": "Ja"}``, order kept."""
    flat: dict[str, str] = {}
    for key, value in tree.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten(value, path))
        else:
            flat[path] = value
    return flat


def unflatten(flat: dict[str, str]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path, value in flat.items():
        node = tree
        *parents, leaf = path.split(".")
        for part in parents:
            node = node.setdefault(part, {})
        node[leaf] = value
    return tree


def read_catalog(locale_dir: Path) -> dict[str, str]:
    """Every message of a locale as ``{"namespace.key.path": text}``."""
    messages: dict[str, str] = {}
    for path in sorted(locale_dir.glob("*.json")):
        messages.update(
            flatten(json.loads(path.read_text(encoding="utf-8")), path.stem)
        )
    return messages


def namespaces(locale_dir: Path) -> list[str]:
    return sorted(path.stem for path in locale_dir.glob("*.json"))


def write_catalog(
    locale_dir: Path,
    messages: dict[str, str],
    order: list[str],
    all_namespaces: list[str],
) -> None:
    """One file per German namespace (empty ones too, since the locale's
    index imports every one), keys in the German order."""
    by_namespace: dict[str, dict[str, str]] = {}
    for key in order:
        if key in messages:
            namespace, rest = key.split(".", 1)
            by_namespace.setdefault(namespace, {})[rest] = messages[key]
    locale_dir.mkdir(parents=True, exist_ok=True)
    for namespace in all_namespaces:
        content = unflatten(by_namespace.get(namespace, {}))
        (locale_dir / f"{namespace}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def source_hash(text: str) -> str:
    return hashlib.sha256(f"{CATALOG_PROMPT_VERSION}\n{text}".encode()).hexdigest()[:16]


def sources_path(messages_dir: Path, locale: str) -> Path:
    return messages_dir / ".sources" / f"{locale}.json"


def read_sources(messages_dir: Path, locale: str) -> dict[str, str]:
    path = sources_path(messages_dir, locale)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_sources(messages_dir: Path, locale: str, sources: dict[str, str]) -> None:
    path = sources_path(messages_dir, locale)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(sorted(sources.items())), indent=2) + "\n", encoding="utf-8"
    )


def pending_keys(
    source: dict[str, str], target: dict[str, str], sources: dict[str, str]
) -> list[str]:
    """Keys to translate: missing, or translated from a German text that has
    changed since. A message with no recorded source is kept as written by
    hand; ``--adopt`` records it."""
    return [
        key
        for key, text in source.items()
        if key not in target or (key in sources and sources[key] != source_hash(text))
    ]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _signature(text: str) -> tuple[list[str], Counter[str], Counter[str]]:
    return (
        sorted(set(_ARGUMENT_RE.findall(text))),
        Counter(_BRANCH_RE.findall(text)),
        Counter(_TAG_RE.findall(text)),
    )


def message_problems(german: str, translated: Optional[str]) -> list[str]:
    """What makes a translated message unfit to ship; empty when it is fit."""
    if translated is None or not translated.strip():
        return ["empty"]
    problems: list[str] = []
    args, branches, tags = _signature(german)
    t_args, t_branches, t_tags = _signature(translated)
    if args != t_args:
        problems.append(f"placeholders {args} became {t_args}")
    if branches != t_branches:
        problems.append("plural/select branches changed")
    if tags != t_tags:
        problems.append("rich-text tags changed")
    if translated.count("{") != translated.count("}"):
        problems.append("unbalanced braces")
    if _RUNAWAY_RE.search(translated) or len(translated) > 3 * len(german) + 40:
        problems.append("runaway text")
    return problems


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------


@dataclass
class CatalogReport:
    pending: list[str] = field(default_factory=list)
    translated: dict[str, str] = field(default_factory=dict)
    failed: dict[str, list[str]] = field(default_factory=dict)


def _segment_line(ref: str, text: str) -> str:
    # One line per segment: newlines inside a message would end it early.
    return f"[{ref}] {text}".replace("\n", "\\n")


def translate_keys(
    builder: DigestBuilder,
    locale: str,
    source: dict[str, str],
    keys: list[str],
) -> CatalogReport:
    report = CatalogReport()
    for start in range(0, len(keys), _BATCH):
        batch = keys[start : start + _BATCH]
        refs = {f"S{i + 1}": key for i, key in enumerate(batch)}
        prompt = format_catalog_prompt(
            locale,
            "\n".join(_segment_line(ref, source[key]) for ref, key in refs.items()),
        )
        try:
            result, _ = builder.call(prompt, TranslationBatch)
            answers = {
                s.ref.strip(): strip_refs(s.text, "S").replace("\\n", "\n")
                for s in result.segments
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Batch of %d messages failed: %s", len(batch), exc)
            answers = {}
        for ref, key in refs.items():
            translated = answers.get(ref)
            problems = message_problems(source[key], translated)
            if problems:
                report.failed[key] = problems
            else:
                assert translated is not None
                report.translated[key] = translated
    return report


def run(
    locale: str,
    messages_dir: Path,
    *,
    builder: Optional[DigestBuilder],
    dry_run: bool = False,
    adopt: bool = False,
) -> CatalogReport:
    source = read_catalog(messages_dir / SOURCE_LOCALE)
    target_dir = messages_dir / locale
    target = read_catalog(target_dir) if target_dir.exists() else {}
    sources = read_sources(messages_dir, locale)

    if adopt:
        for key in source:
            if key in target:
                sources[key] = source_hash(source[key])
        write_sources(messages_dir, locale, sources)
        return CatalogReport()

    keys = pending_keys(source, target, sources)
    if dry_run or not keys:
        return CatalogReport(pending=keys)
    assert builder is not None
    report = translate_keys(builder, locale, source, keys)
    report.pending = keys

    target.update(report.translated)
    # Messages German no longer has are dropped with it.
    target = {key: value for key, value in target.items() if key in source}
    for key in report.translated:
        sources[key] = source_hash(source[key])
    sources = {key: value for key, value in sources.items() if key in source}
    write_catalog(
        target_dir, target, list(source), namespaces(messages_dir / SOURCE_LOCALE)
    )
    write_sources(messages_dir, locale, sources)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Translate the web's UI catalogs from German into a locale."
    )
    parser.add_argument("--locale", required=True, help="Target locale, e.g. fr")
    parser.add_argument(
        "--messages-dir", type=Path, default=DEFAULT_MESSAGES_DIR, help="web/messages"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List pending keys, call no model"
    )
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="Record the existing translations as current (hand-written catalogs)",
    )
    args = parser.parse_args(argv)
    if args.locale == SOURCE_LOCALE:
        print("German is the source catalog.", file=sys.stderr)
        return 2

    builder = None if args.dry_run or args.adopt else DigestBuilder()
    try:
        report = run(
            args.locale,
            args.messages_dir,
            builder=builder,
            dry_run=args.dry_run,
            adopt=args.adopt,
        )
    finally:
        if builder is not None:
            builder.close()

    if args.adopt:
        print(f"recorded the current {args.locale} translations as up to date")
        return 0
    if args.dry_run:
        print(f"{len(report.pending)} messages pending for {args.locale}")
        for key in report.pending:
            print(f"  {key}")
        return 0
    print(f"translated={len(report.translated)} failed={len(report.failed)}")
    for key, problems in report.failed.items():
        print(f"  {key}: {', '.join(problems)}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # Same native-extension teardown crash as the feed builder after Gemini calls.
    os._exit(exit_code)
