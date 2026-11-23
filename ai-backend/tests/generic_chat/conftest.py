# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Fakes for the generic chat: corpus, feed, parties and quick replies are
in-memory; no LLM, Qdrant, Firestore or Perplexity is reached."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import pytest

from src.generic_chat.schemas import GenericChatDeps
from src.models.context import Context, ContextParty

POLL_ID = 6123
VOTE_DAY = "2026-11-13"
TODAY = date(2026, 11, 16)
DEBATE_ID = "bundestag_2026-11-13_d185-top20"
VOTE_ITEM_ID = f"bundestag_{VOTE_DAY}_v{POLL_ID}"
SPEECH_IDS = [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222",
]


def general_context() -> Context:
    return Context(
        context_id="bundestag-aktuell",
        name="Bundestag aktuell",
        short_name="Bundestag",
        type="general",
        location_name="Deutschland",
        supports_swiper=False,
        supports_voting_behavior=False,
        relevant_area=None,
        region_path=["DE"],
        level="federal",
        legislature_period_id=161,
    )


def parties() -> list[ContextParty]:
    def party(pid: str, name: str, in_parliament: bool) -> ContextParty:
        return ContextParty(
            party_id=pid,
            name=name,
            long_name=f"{name} long",
            website_url=f"https://{pid}.de",
            is_already_in_parliament=in_parliament,
        )

    return [party("spd", "SPD", True), party("cdu", "CDU/CSU", True), party("volt", "Volt", False)]


def make_deps(language: str = "de") -> GenericChatDeps:
    return GenericChatDeps(
        context=general_context(),
        parties=parties(),
        language=language,  # type: ignore[arg-type]
        session_id="s-1",
    )


def vote_payload(poll_id: int = POLL_ID) -> dict:
    return {
        "source_type": "vote_record",
        "external_id": poll_id,
        "chunk_index": 0,
        "citation_title": "Gesetz zur Verlängerung der Mietpreisbremse",
        "citation_url": f"https://www.abgeordnetenwatch.de/poll/{poll_id}",
        "publish_date": VOTE_DAY,
        "region": "DE",
        "text": "Antrag zur Verlängerung der Mietpreisbremse.",
        "meta": {
            "motion_outcome": "angenommen",
            "vote_results": [
                {"party_id": "spd", "stance": "agree", "yes": 120, "no": 0, "abstain": 1, "no_show": 4},
                {"party_id": "cdu", "stance": "agree", "yes": 180, "no": 2, "abstain": 0, "no_show": 6},
            ],
        },
    }


def speech_chunk(speech_id: str, index: int, text: str, party_id: str = "spd") -> dict:
    return {
        "source_type": "parliamentary_speech",
        "source_item_id": speech_id,
        "chunk_index": index,
        "party_id": party_id,
        "source": "dip",
        "citation_title": f"Rede {speech_id[:4]}",
        "citation_url": f"https://dserver.bundestag.de/btp/21/21185.pdf#page={3 + index}",
        "publish_date": VOTE_DAY,
        "region": "DE",
        "text": text,
        "meta": {"speaker_name": f"Speaker {speech_id[:4]}"},
    }


def manifesto_payload(party_id: str = "volt") -> dict:
    return {
        "source_type": "party_manifesto",
        "party_id": party_id,
        "citation_title": f"{party_id} Wahlprogramm 2025",
        "citation_url": f"https://{party_id}.de/programm.pdf#page=12",
        "publish_date": "2025-02-23",
        "region": "DE",
        "text": "Wir wollen bezahlbare Mieten.",
        "meta": {"page_start": 12},
    }


def feed_item(
    item_id: str,
    kind: str,
    *,
    day: str = VOTE_DAY,
    status: str = "published",
    speech_ids: Optional[list[str]] = None,
    drucksachen: Optional[list[str]] = None,
) -> dict:
    item: dict[str, Any] = {
        "id": item_id,
        "kind": kind,
        "parliament": "bundestag",
        "date": day,
        "status": status,
        "content": {
            "de": {"headline": f"Schlagzeile {item_id}"},
            "en": {"headline": f"Headline {item_id}"},
        },
        "format_version": "7",
    }
    if kind == "debate":
        item["debate"] = {
            "agenda_item": "TOP 20 Mietpreisbremse",
            "drucksachen": drucksachen or ["21/1234"],
            **({"speech_ids": speech_ids} if speech_ids is not None else {}),
        }
    else:
        item["vote"] = {
            "poll_id": POLL_ID,
            "official_title": "Mietpreisbremse",
            "outcome": "angenommen",
            "drucksachen": drucksachen or ["21/1234"],
        }
    return item


def _in_range(payload: dict, window: Any) -> bool:
    if window is None:
        return True
    day = str(payload.get("publish_date"))[:10]
    return (
        (window.gte is None or day >= window.gte.date().isoformat())
        and (window.lte is None or day <= window.lte.date().isoformat())
        and (window.lt is None or day < window.lt.date().isoformat())
    )

def retrieve_signature_check(query: str, **kwargs: Any) -> None:
    """Fakes of retrieve() accept only what the real one does."""
    import inspect

    from src.retrieve import retrieve

    inspect.signature(retrieve).bind(query, **kwargs)


@dataclass
class FakeIO:
    """Records every call the tools make to the corpus and the feed."""

    retrieve_calls: list[dict] = field(default_factory=list)
    fetch_calls: list[dict] = field(default_factory=list)
    feed_list_calls: list[dict] = field(default_factory=list)
    retrieve_results: dict[str, list[tuple[dict, float]]] = field(default_factory=dict)
    votes: dict[int, list[dict]] = field(default_factory=dict)
    speeches: list[dict] = field(default_factory=list)
    feed: dict[str, dict] = field(default_factory=dict)

    async def embed_query(self, query: str) -> list[float]:
        return [0.0] * 8

    async def retrieve(self, query: str, **kwargs: Any) -> list:
        retrieve_signature_check(query, **kwargs)
        self.retrieve_calls.append({"query": query, **kwargs})
        hits = [
            (payload, score)
            for payload, score in self.retrieve_results.get(kwargs.get("source_type", ""), [])
            if score >= (kwargs.get("score_threshold") or 0)
            and _in_range(payload, kwargs.get("publish_range"))
        ][: kwargs.get("limit", 5)]
        if kwargs.get("with_scores"):
            return list(hits)
        return [payload for payload, _ in hits]

    async def fetch_payloads(self, source_type: str, **kwargs: Any) -> list[dict]:
        self.fetch_calls.append({"source_type": source_type, **kwargs})
        if source_type == "vote_record":
            return list(self.votes.get(kwargs.get("external_id"), []))
        wanted = set(kwargs.get("source_item_ids") or [])
        return [c for c in self.speeches if c["source_item_id"] in wanted]

    async def aget_feed_item(self, item_id: str) -> Optional[dict]:
        return self.feed.get(item_id)

    async def aget_feed_items(self, parliament: str, since, until, kind=None, limit=200) -> list[dict]:
        self.feed_list_calls.append({"parliament": parliament, "since": since, "until": until, "kind": kind})
        items = [
            i
            for i in self.feed.values()
            if i["parliament"] == parliament
            and since.isoformat() <= i["date"] <= until.isoformat()
            and i.get("status", "published") == "published"
            and (kind is None or i["kind"] == kind)
        ]
        return sorted(items, key=lambda i: i["date"], reverse=True)


@pytest.fixture()
def fake_io(monkeypatch: pytest.MonkeyPatch) -> FakeIO:
    io = FakeIO()
    import src.generic_chat.tools as tools

    monkeypatch.setattr(tools, "embed_query", io.embed_query)
    monkeypatch.setattr(tools, "retrieve", io.retrieve)
    monkeypatch.setattr(tools, "fetch_payloads", io.fetch_payloads)
    monkeypatch.setattr(tools, "aget_feed_item", io.aget_feed_item)
    monkeypatch.setattr(tools, "aget_feed_items", io.aget_feed_items)
    monkeypatch.setattr(tools, "_today", lambda: TODAY)
    return io


@pytest.fixture(autouse=True)
def _no_press(monkeypatch: pytest.MonkeyPatch) -> None:
    """No web search from tests; test_web_context switches it on."""
    from src.generic_chat import web_context

    monkeypatch.setenv(web_context.ENV, "off")


@pytest.fixture(autouse=True)
def _no_citation_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """No check model from tests; test_presets switches it on with a fake."""
    from src.generic_chat import citation_check

    monkeypatch.setenv(citation_check.ENV, "off")


@pytest.fixture(autouse=True)
def _no_related_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """No feed search from tests; test_related switches it on with a fake."""
    from src.generic_chat import related

    monkeypatch.setenv(related.ENV, "off")
    monkeypatch.setattr(related, "_unavailable_until", {})
