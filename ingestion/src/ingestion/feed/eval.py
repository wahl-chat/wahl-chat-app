# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Party positions against a hand-checked gold set.

A wrong position under a party's name is the most damaging mistake the feed
can make, so a change to its prompts or models is measured before it ships.

``--make-gold`` (once): picks debates from the corpus, freezes their speeches
in ``data/feed_eval/debates.json`` and drafts reference positions with the
strongest Gemini Pro at the highest thinking level into
``gold_positions.json``. A draft counts as gold only once a person has read it
against the speeches and filled in ``checked_by`` / ``checked_at`` (and fixed
the sentence where needed).

Without it: runs the current prompts and publication roster over the frozen
debates, exactly as a build would, and reports per Fraktion whether a
position was written and verified and whether it agrees with gold.

Usage (from the repo root):
    make eval-feed ARGS="--make-gold --since 2026-06-01"
    make eval-feed
"""

from __future__ import annotations

# Load the env file before the imports below: COLLECTION_NAME and the
# embedding settings are read at import time. override=False keeps exported
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

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Coroutine, Optional, TypeVar

from ingestion.feed.builder import (
    NO_FRAKTION,
    DayPlan,
    DebateUnit,
    FeedBuilder,
    Fraktionen,
    build_debate,
    plan_days,
    speeches_block,
)
from ingestion.feed.parliaments import PARLIAMENTS, Parliament, load_party_display
from ingestion.feed.prompts import (
    PositionAgreementBatch,
    PositionsDraft,
    format_agreement_prompt,
    format_positions_prompt,
)
from ingestion.feed.reader import AgendaItem, Speech

logger = logging.getLogger(__name__)
T = TypeVar("T")

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "feed_eval"
# One file per debate: a whole debate is up to ~150 KB, and the repo refuses
# files over 500 KB.
DEBATES_DIR = DATA_DIR / "debates"
GOLD_FILE = DATA_DIR / "gold_positions.json"
# The strongest Gemini Pro on Vertex; used only to draft gold, never in a build.
GOLD_MODEL = "gemini-3.1-pro-preview"
_GOLD_TIMEOUT_S = 600
_DEFAULT_COUNT = 20
# Question formats, not debates: there is no position to summarise.
_NOT_A_DEBATE = re.compile(r"Befragung|Fragestunde", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Frozen debates
# ---------------------------------------------------------------------------


def snapshot(unit: DebateUnit, day: date) -> dict[str, Any]:
    return {
        "id": unit.item_id,
        "day": day.isoformat(),
        "agenda": unit.agenda.label,
        "speeches": [
            {"speaker": s.speaker, "party_id": s.party_id, "text": s.text}
            for s in unit.agenda.speeches
        ],
    }


def unit_from_snapshot(debate: dict[str, Any]) -> tuple[DayPlan, DebateUnit]:
    day = date.fromisoformat(debate["day"])
    speeches = [
        Speech(
            source_item_id=f"{debate['id']}-{n}",
            source="op",
            day=day,
            speaker=s["speaker"],
            party_id=s["party_id"],
            text=s["text"],
            citation_title=None,
            citation_url=None,
            agenda_slug="",
            agenda_title=debate["agenda"],
            agenda_official=None,
            video_uri=None,
            protocol_id=None,
            pdf_url=None,
            session_key=None,
        )
        for n, s in enumerate(debate["speeches"])
    ]
    unit = DebateUnit(
        item_id=debate["id"],
        agenda=AgendaItem(
            key=debate["id"], label=debate["agenda"], speeches=speeches, ordered=True
        ),
        protocols=[],
        input_hash="eval",
    )
    edition_id = debate["id"].rsplit("_d", 1)[0]
    return DayPlan(day, edition_id, [], [unit], []), unit


def required_fraktionen(parliament: Parliament, speeches: list[Speech]) -> list[str]:
    by_party = Fraktionen(dict(parliament.party_aliases)).speeches_by(speeches)
    return [p for p in by_party if p not in NO_FRAKTION]


def select_debates(
    parliament: Parliament, plans: list[DayPlan], count: int
) -> list[tuple[DebateUnit, date]]:
    """Real debates (three or more Fraktionen, no question time), spread
    evenly from the shortest to the longest."""
    candidates = [
        (unit, plan.day)
        for plan in plans
        for unit in plan.debates
        if unit.buildable
        and not _NOT_A_DEBATE.search(unit.agenda.label)
        and len(required_fraktionen(parliament, unit.agenda.speeches)) >= 3
    ]
    candidates.sort(key=lambda c: (len(c[0].agenda.speeches), c[0].item_id))
    if len(candidates) <= count:
        return candidates
    step = (len(candidates) - 1) / (count - 1)
    return [candidates[round(i * step)] for i in range(count)]


async def _limited(
    builder: FeedBuilder, coroutines: list[Coroutine[Any, Any, T]]
) -> list[T]:
    """All results, in order, with no more running at once than a build allows."""
    semaphore = asyncio.Semaphore(builder.concurrency)

    async def one(coroutine: Coroutine[Any, Any, T]) -> T:
        async with semaphore:
            return await coroutine

    return list(await asyncio.gather(*(one(c) for c in coroutines)))


# ---------------------------------------------------------------------------
# Gold drafts
# ---------------------------------------------------------------------------


def _gold_builder() -> FeedBuilder:
    from ingestion.llm_clients import (  # noqa: PLC0415
        RosterLLM,
        gemini,
        structured_output_with_failover,
    )
    from wahlchat_common.vertex_credentials import vertex_enabled  # noqa: PLC0415

    vertex = vertex_enabled()
    if not vertex:
        logger.warning("Vertex AI not configured; drafting gold via Google AI Studio.")
    roster = [
        RosterLLM(
            GOLD_MODEL,
            gemini(
                GOLD_MODEL,
                vertex=vertex,
                thinking_level="high",
                timeout=_GOLD_TIMEOUT_S,
            ),
            100,
        )
    ]

    async def fn(messages: list, schema: type) -> tuple[Any, str]:
        return await structured_output_with_failover(roster, messages, schema)

    return FeedBuilder(fn)


async def _draft_gold(
    builder: FeedBuilder, parliament: Parliament, debate: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    _, unit = unit_from_snapshot(debate)
    speeches = unit.agenda.speeches
    wanted = required_fraktionen(parliament, speeches)
    draft, model = await builder.acall(
        format_positions_prompt(
            parliament.name,
            unit.agenda.label,
            ", ".join(wanted),
            speeches_block(speeches),
        ),
        PositionsDraft,
    )
    fraktionen = Fraktionen(dict(parliament.party_aliases))
    positions: dict[str, dict[str, Any]] = {}
    for position in draft.positions:
        party_id = fraktionen.of(position.party_id)
        if party_id in wanted and party_id not in positions:
            positions[party_id] = {
                "position": position.position.strip(),
                "drafted_by": model,
                "checked_by": None,
                "checked_at": None,
                "note": "",
            }
    for party_id in wanted:
        positions.setdefault(
            party_id,
            {
                "position": "",
                "drafted_by": model,
                "checked_by": None,
                "checked_at": None,
                "note": "no draft: write it by hand",
            },
        )
    return positions


def make_gold(
    parliament: Parliament, since: Optional[date], days: int, count: int
) -> int:
    from qdrant_client import QdrantClient  # noqa: PLC0415

    from ingestion.feed.bulk import load_sources  # noqa: PLC0415

    if DEBATES_DIR.exists() or GOLD_FILE.exists():
        print(
            f"{DATA_DIR} already holds a gold set; move it away to draft a new one.",
            file=sys.stderr,
        )
        return 2
    qdrant = QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )
    sources = load_sources(qdrant, parliament, days, since=since)
    if sources is None:
        print("No corpus data.", file=sys.stderr)
        return 1
    chosen = select_debates(
        parliament, plan_days(parliament, sources.votes, sources.sitting_days), count
    )
    debates = [snapshot(unit, day) for unit, day in chosen]
    builder = _gold_builder()

    async def draft_all() -> list[dict[str, dict[str, Any]]]:
        return list(
            await asyncio.gather(
                *(_draft_gold(builder, parliament, d) for d in debates)
            )
        )

    try:
        drafts = builder.run(draft_all())
    finally:
        builder.close()
    DEBATES_DIR.mkdir(parents=True, exist_ok=True)
    for debate in debates:
        _write_json(DEBATES_DIR / f"{debate['id']}.json", debate)
    _write_json(GOLD_FILE, {d["id"]: g for d, g in zip(debates, drafts)})
    print(
        f"Froze {len(debates)} debates and drafted their positions with "
        f"{GOLD_MODEL}.\nCheck every entry in {GOLD_FILE} against the speeches "
        "and fill in checked_by / checked_at; only checked entries count as gold."
    )
    return 0


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


@dataclass
class DebateScore:
    id: str
    required: list[str]
    written: dict[str, str] = field(default_factory=dict)
    # party -> (agrees, reason), only where both gold and a sentence exist.
    agreement: dict[str, tuple[bool, str]] = field(default_factory=dict)

    @property
    def missing(self) -> list[str]:
        return [p for p in self.required if p not in self.written]


async def _judge(
    builder: FeedBuilder, agenda: str, pairs: dict[str, tuple[str, str]]
) -> dict[str, tuple[bool, str]]:
    if not pairs:
        return {}
    refs = {f"P{i + 1}": party_id for i, party_id in enumerate(pairs)}
    lines = "\n".join(
        f"[{ref}] {party_id}\nA: {pairs[party_id][0]}\nB: {pairs[party_id][1]}"
        for ref, party_id in refs.items()
    )
    result, _ = await builder.acall(
        format_agreement_prompt(agenda, lines), PositionAgreementBatch
    )
    return {
        refs[p.ref.strip()]: (p.agrees, p.reason)
        for p in result.pairs
        if p.ref.strip() in refs
    }


async def _score(
    builder: FeedBuilder,
    parliament: Parliament,
    display: dict[str, Any],
    debate: dict[str, Any],
    gold: dict[str, str],
) -> DebateScore:
    plan, unit = unit_from_snapshot(debate)
    item = await build_debate(
        builder, parliament, plan, unit, display, datetime.now(timezone.utc)
    )
    score = DebateScore(
        debate["id"], required_fraktionen(parliament, unit.agenda.speeches)
    )
    if item is None:
        return score
    score.written = {p.party_id: p.text for p in item.content["de"].positions}
    pairs = {
        party_id: (gold[party_id], text)
        for party_id, text in score.written.items()
        if gold.get(party_id)
    }
    try:
        score.agreement = await _judge(builder, unit.agenda.label, pairs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Judging %s failed: %s", debate["id"], exc)
    return score


def _gold_sentences(
    entries: dict[str, dict[str, Any]], include_unchecked: bool
) -> dict[str, str]:
    return {
        party_id: entry["position"]
        for party_id, entry in entries.items()
        if entry.get("position") and (include_unchecked or entry.get("checked_by"))
    }


def evaluate(parliament: Parliament, env: str, include_unchecked: bool) -> int:
    debates = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(DEBATES_DIR.glob("*.json"))
    ]
    gold_file = json.loads(GOLD_FILE.read_text(encoding="utf-8"))
    gold = {
        debate_id: _gold_sentences(entries, include_unchecked)
        for debate_id, entries in gold_file.items()
    }
    checked = sum(len(g) for g in gold.values())
    if checked == 0:
        print(
            "No checked gold entries yet: fill in checked_by in "
            f"{GOLD_FILE}, or pass --include-unchecked to compare with the drafts.",
            file=sys.stderr,
        )
        return 2
    display = load_party_display(parliament, env)
    builder = FeedBuilder()

    async def score_all() -> list[DebateScore]:
        return await _limited(
            builder,
            [
                _score(builder, parliament, display, d, gold.get(d["id"], {}))
                for d in debates
            ],
        )

    try:
        scores = builder.run(score_all())
    finally:
        builder.close()
    return report(scores)


def report(scores: list[DebateScore]) -> int:
    required = sum(len(s.required) for s in scores)
    missing = sum(len(s.missing) for s in scores)
    judged = sum(len(s.agreement) for s in scores)
    agreed = sum(1 for s in scores for ok, _ in s.agreement.values() if ok)
    for score in scores:
        line = f"{score.id}: {len(score.written)}/{len(score.required)} written" + (
            f", missing {score.missing}" if score.missing else ""
        )
        print(line)
        for party_id, (ok, reason) in score.agreement.items():
            if not ok:
                print(f"    disagrees for {party_id}: {reason}")
    print(
        f"\nFraktionen with a verified position: {required - missing}/{required}\n"
        f"Agreeing with gold: {agreed}/{judged}"
    )
    return 0 if missing == 0 and agreed == judged else 1


def _write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Evaluate the feed's party positions against the gold set."
    )
    parser.add_argument(
        "--make-gold",
        action="store_true",
        help=f"Freeze debates from the corpus and draft gold with {GOLD_MODEL}",
    )
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="With --make-gold: pick debates from this day on",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=56,
        help="With --make-gold and no --since: window length (default: 56)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=_DEFAULT_COUNT,
        help=f"With --make-gold: how many debates (default: {_DEFAULT_COUNT})",
    )
    parser.add_argument(
        "--include-unchecked",
        action="store_true",
        help="Also compare against drafts nobody has checked yet",
    )
    args = parser.parse_args(argv)
    parliament = PARLIAMENTS["bundestag"]
    if args.make_gold:
        return make_gold(parliament, args.since, args.days, args.count)
    return evaluate(parliament, os.getenv("ENV", "dev"), args.include_unchecked)


if __name__ == "__main__":
    exit_code = main()
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    # Skip interpreter teardown: after any Gemini call a native extension
    # segfaults while being finalized (see feed.bulk).
    os._exit(exit_code)
