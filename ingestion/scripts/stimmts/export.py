"""Draft Stimmt's? puzzles from Abgeordnetenwatch and the Bundestag's DIP.

Run from ingestion/ (needs DIP_API_KEY in ingestion/.env or ai-backend/.env):

    PYTHONPATH=src:../packages/wahlchat-common/src:scripts uv run python -m stimmts.export

    --refresh   fetch everything again instead of reusing output/
    --no-dip    skip the Drucksachen (no key needed); drafts get no document

It writes, in scripts/stimmts/output/ (gitignored):
  votes.json   every roll-call vote of the term with per-party counts
  dip.json     the DIP records of the picks' Drucksachen
  drafts.json  one draft puzzle per pick: counts, answers and document filled
               in, title, briefing and "Ja bedeutet …" left for a person to
               write, and `_review` notes on anything to check
and regenerates docs/stimmts/puzzle-selection.md.

The game never reads any of this: a draft becomes a puzzle only once a person
has written its text, checked it, and committed it to
web/lib/stimmts/content/puzzles.json (see docs/stimmts/CONTENT.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from wahlchat_common.legislature_config import (
    FEDERAL_LEGISLATURE_IDS,
    LEGISLATURE_CONFIG,
)

from ingestion.connectors.abgeordnetenwatch.client import AWClient
from ingestion.connectors.bundestag_speeches.client import DipClient

from .drucksachen import document, number_from_url
from .report import selection_report
from .selection import PICKS, SPARES
from .votes import (
    drucksache_urls,
    intro_text,
    outcome_problem,
    tally_parties,
    vote_problems,
)

INGESTION = Path(__file__).resolve().parents[2]
REPO = INGESTION.parent
OUTPUT = Path(__file__).resolve().parent / "output"
PUZZLES = REPO / "web" / "lib" / "stimmts" / "content" / "puzzles.json"
SELECTION_DOC = REPO / "docs" / "stimmts" / "puzzle-selection.md"

WAHLPERIODE = 21

# Abgeordnetenwatch's topic names, cut to the length of the game's topic line.
SHORT_TOPICS = {
    "Öffentliche Finanzen, Steuern und Abgaben": "Steuern und Finanzen",
    "Außenpolitik und internationale Beziehungen": "Außenpolitik",
    "Gesellschaftspolitik, soziale Gruppen": "Soziales",
    "Migration und Aufenthaltsrecht": "Migration",
    "Raumordnung, Bau- und Wohnungswesen": "Wohnen",
    "Politisches Leben, Parteien": "Demokratie",
    "Europapolitik und Europäische Union": "Europa",
    "Sport, Freizeit und Tourismus": "Sport",
    "Arbeit und Beschäftigung": "Arbeit",
    "Bildung und Erziehung": "Bildung",
}


def legislature_id() -> int:
    return next(
        period_id
        for period_id in FEDERAL_LEGISLATURE_IDS
        if LEGISLATURE_CONFIG[period_id].wahlperiode == WAHLPERIODE
    )


def slugify(title: str) -> str:
    """'Änderung des Stromsteuergesetzes' becomes 'aenderung-des-stromsteuergesetzes'."""
    text = title.replace("­", "").lower()
    for umlaut, spelled in {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}.items():
        text = text.replace(umlaut, spelled)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if len(slug) > 60:
        slug = slug[:60].rsplit("-", 1)[0]
    return slug


def read_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def fetch_polls() -> list[dict]:
    client = AWClient()
    polls = client.get_all("polls", {"field_legislature": legislature_id()})
    print(f"Abgeordnetenwatch: {len(polls)} roll-call votes, fetching the results …")
    rows = []
    for index, poll in enumerate(polls, 1):
        parties, unaffiliated = tally_parties(client.get_votes_for_poll(poll["id"]))
        intro = poll.get("field_intro") or ""
        rows.append(
            {
                "id": poll["id"],
                "date": poll["field_poll_date"],
                "title": poll["label"].replace("­", ""),
                "topics": [t["label"] for t in poll.get("field_topics") or []],
                "accepted": poll.get("field_accepted"),
                "url": poll.get("abgeordnetenwatch_url"),
                "parties": parties,
                "unaffiliated": unaffiliated,
                "intro": intro_text(intro),
                "drucksachen": drucksache_urls(intro),
            }
        )
        if index % 10 == 0:
            print(f"  {index}/{len(polls)}")
    return rows


def dip_client() -> DipClient:
    env = INGESTION / ".env"
    if not env.exists():
        env = REPO / "ai-backend" / ".env"
    if env.exists():
        load_dotenv(env, override=False)
    key = os.environ.get("DIP_API_KEY")
    if not key:
        sys.exit("DIP_API_KEY is not set (ingestion/.env or ai-backend/.env).")
    return DipClient(key, sleep=0.5)


def fetch_drucksachen(numbers: list[str], cache: dict) -> dict:
    missing = [number for number in numbers if number not in cache]
    if not missing:
        return cache
    client = dip_client()
    print(f"DIP: fetching {len(missing)} Drucksachen …")
    for number in missing:
        period = number.split("/")[0]
        data = client.get(
            "/drucksache", {"f.dokumentnummer": number, "f.wahlperiode": period}
        )
        documents = data.get("documents") or []
        cache[number] = documents[0] if documents else None
    return cache


def committed_differences(draft: dict, committed: dict) -> list[str]:
    """Where the fetched facts disagree with a puzzle already in the game."""
    notes = []
    if draft["parties"] != committed.get("parties"):
        notes.append("the counts differ from the committed puzzle")
    if draft["unaffiliated"] != committed.get("unaffiliated"):
        notes.append("the members without a Fraktion differ from the committed puzzle")
    if draft["outcome"] != committed.get("outcome"):
        notes.append("the outcome differs from the committed puzzle")
    if "document" in draft and "document" in committed:
        for field in ("type", "number", "date", "title", "url", "initiator"):
            if draft["document"].get(field) != committed["document"].get(field):
                notes.append(f"document {field} differs from the committed puzzle")
    return notes


def draft_puzzle(poll: dict, why: str, dip: dict | None, committed: dict | None):
    notes = vote_problems(poll["parties"], poll["unaffiliated"])
    outcome = outcome_problem(poll["parties"], poll["accepted"])
    if outcome:
        notes.append(outcome)
    numbers = [n for n in map(number_from_url, poll["drucksachen"]) if n]
    draft: dict = {
        "id": committed["id"] if committed else slugify(poll["title"]),
        "voteDate": poll["date"],
        "topic": (committed or {}).get("topic")
        or SHORT_TOPICS.get(poll["topics"][0] if poll["topics"] else "", "")
        or (poll["topics"][0] if poll["topics"] else ""),
        "title": (committed or {}).get("title", ""),
        "briefing": (committed or {}).get("briefing", ""),
        "yesMeans": (committed or {}).get("yesMeans", ""),
        "outcome": "accepted" if poll["accepted"] else "rejected",
        "parties": [
            {
                key: party[key]
                for key in ("partyId", "answer", "yes", "no", "abstain", "noShow")
            }
            for party in poll["parties"]
        ],
        "unaffiliated": poll["unaffiliated"],
    }
    if dip is not None:
        records = [dip[n] for n in numbers if dip.get(n)]
        missing = [n for n in numbers if not dip.get(n)]
        if missing:
            notes.append(f"not found in DIP: {', '.join(missing)}")
        found, document_notes = document(records)
        notes += document_notes
        if found:
            draft["document"] = found
    draft["source"] = {"label": "Abgeordnetenwatch", "url": poll["url"]}
    if committed:
        notes += committed_differences(draft, committed)
    draft["_review"] = {
        "poll": poll["id"],
        "why": why,
        "awTitle": poll["title"],
        "awTopics": poll["topics"],
        "drucksachen": numbers,
        # Abgeordnetenwatch's own description: a source for the briefing, but
        # it gives the result away, so it is never copied into the game.
        "awDescription": poll["intro"],
        "existing": committed is not None,
        "notes": notes,
    }
    return draft


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-dip", action="store_true")
    args = parser.parse_args()

    votes_path = OUTPUT / "votes.json"
    polls = None if args.refresh else read_json(votes_path, None)
    if polls is None:
        polls = fetch_polls()
        write_json(votes_path, polls)
    by_id = {poll["id"]: poll for poll in polls}
    unknown = [poll_id for poll_id in [*PICKS, *SPARES] if poll_id not in by_id]
    if unknown:
        sys.exit(f"Not roll-call votes of this term: {unknown}")

    dip = None
    if not args.no_dip:
        dip_path = OUTPUT / "dip.json"
        numbers = sorted(
            {
                number
                for poll_id in [*PICKS, *SPARES]
                for number in map(number_from_url, by_id[poll_id]["drucksachen"])
                if number
            }
        )
        dip = fetch_drucksachen(
            numbers, {} if args.refresh else read_json(dip_path, {})
        )
        write_json(dip_path, dip)

    committed = {puzzle["source"]["url"]: puzzle for puzzle in read_json(PUZZLES, [])}
    drafts = [
        draft_puzzle(by_id[poll_id], why, dip, committed.get(by_id[poll_id]["url"]))
        for poll_id, why in PICKS.items()
    ]
    write_json(OUTPUT / "drafts.json", drafts)
    SELECTION_DOC.write_text(selection_report(polls, PICKS, SPARES))

    with_document = sum("document" in draft for draft in drafts)
    print(
        f"\n{len(drafts)} drafts, {with_document} with a Drucksache, "
        f"{sum(d['_review']['existing'] for d in drafts)} already in the game."
    )
    for draft in drafts:
        for note in draft["_review"]["notes"]:
            print(f"  {draft['_review']['poll']} {draft['id']}: {note}")
    print(f"\nWrote {OUTPUT / 'drafts.json'}\nWrote {SELECTION_DOC}")


if __name__ == "__main__":
    main()
