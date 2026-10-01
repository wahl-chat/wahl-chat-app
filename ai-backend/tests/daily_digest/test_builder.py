# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date, datetime, timezone
from typing import Any, Iterator

import pytest

from src.daily_digest.builder import (
    DigestBuilder,
    build_digests,
    compute_input_hash,
    session_from_draft,
    vote_description,
)
from src.daily_digest.parliaments import PARLIAMENTS, PartyDisplay
from src.daily_digest.prompts import (
    SessionSectionDraft,
    SessionSummaryDraft,
    VoteEnrichment,
    VoteEnrichmentBatch,
)
from src.daily_digest.reader import assemble_speeches, group_sitting_days

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
BUNDESTAG = PARLIAMENTS["bundestag"]
DISPLAY = {
    "cdu": PartyDisplay("CDU/CSU", "#000000"),
    "spd": PartyDisplay("SPD", "#E4001B"),
}


def _vote(poll_id: int, day: str = "2026-09-24") -> dict:
    return {
        "external_id": poll_id,
        "publish_date": day,
        "citation_title": f"Antrag {poll_id}",
        "citation_url": f"https://www.abgeordnetenwatch.de/poll/{poll_id}",
        "text": f"Antrag {poll_id}\n\nKontext: Worum es geht.",
        "content_hash": f"vote-{poll_id}",
        "meta": {
            "motion_outcome": "angenommen",
            "vote_results": [
                {"party_id": "cdu", "yes": 200, "no": 0, "abstain": 0, "no_show": 8},
                {"party_id": "spd", "yes": 110, "no": 3, "abstain": 1, "no_show": 6},
                {
                    "party_id": "fraktionslos",
                    "yes": 0,
                    "no": 2,
                    "abstain": 0,
                    "no_show": 1,
                },
            ],
        },
    }


def _sitting_days() -> dict:
    payloads = [
        {
            "source_item_id": "s1",
            "source": "op",
            "speech_key": "de-21-45-anna-top1",
            "text": "Wir brauchen mehr Wohnungen.",
            "chunk_index": 0,
            "publish_date": "2026-09-24",
            "party_id": "spd",
            "citation_url": "https://video/1.mp4#t=3",
            "citation_title": "Anna, 2026-09-24 (Video, TOP 1)",
            "content_hash": "speech-1",
            "meta": {
                "agenda_item_title": "Wohnungsbau",
                "video_uri": "https://video/1.mp4",
                "speaker_name": "Anna",
            },
        }
    ]
    return group_sitting_days(assemble_speeches(payloads))


class FakeLLM:
    def __init__(self, fail_votes: bool = False, fail_session: bool = False) -> None:
        self.fail_votes = fail_votes
        self.fail_session = fail_session
        self.calls: list[tuple[type, bool]] = []

    async def __call__(self, messages: list, schema: type, long_form: bool) -> Any:
        self.calls.append((schema, long_form))
        if schema is VoteEnrichmentBatch:
            if self.fail_votes:
                raise RuntimeError("quota")
            refs = [
                line.split("]")[0][1:]
                for line in messages[0].content.split("\n")
                if line.startswith("[V")
            ]
            return VoteEnrichmentBatch(
                votes=[
                    VoteEnrichment(
                        ref=ref,
                        topics=[
                            "housing_rent",
                            "housing_rent",
                            "economy_finance",
                            "social_labor",
                        ],
                        short_title=f"Kurz {ref}",
                        summary="Ein Satz.",
                    )
                    for ref in refs
                ]
            )
        if self.fail_session:
            raise RuntimeError("quota")
        return SessionSummaryDraft(
            sections=[
                SessionSectionDraft(
                    topic="housing_rent",
                    headline="Mehr Wohnungen",
                    summary="Die SPD fordert mehr Wohnungsbau.",
                    agenda_refs=["A1"],
                ),
                SessionSectionDraft(
                    topic="health_care",
                    headline="Erfunden",
                    summary="Nicht in den Auszügen.",
                    agenda_refs=["A99"],
                ),
            ],
            other_topics=[],
        )


@pytest.fixture()
def fake_llm() -> Iterator[FakeLLM]:
    yield FakeLLM()


def _build(llm: FakeLLM, **kwargs: Any) -> tuple[list, int]:
    builder = DigestBuilder(llm)
    try:
        return build_digests(
            BUNDESTAG,
            kwargs.pop("votes", [_vote(1), _vote(2)]),
            kwargs.pop("sittings", _sitting_days()),
            DISPLAY,
            builder,
            now=NOW,
            **kwargs,
        )
    finally:
        builder.close()


def test_builds_one_digest_per_day_with_enriched_votes(fake_llm: FakeLLM) -> None:
    digests, unchanged = _build(fake_llm)
    assert unchanged == 0
    [digest] = digests
    assert digest.id == "bundestag_2026-09-24"
    assert [v.short_title for v in digest.votes] == ["Kurz V1", "Kurz V2"]
    # Deduplicated and capped at two topics.
    assert digest.votes[0].topics == ["housing_rent", "economy_finance"]
    assert digest.input_hash is not None


def test_vote_parties_carry_display_names_and_fallbacks(fake_llm: FakeLLM) -> None:
    [digest], _ = _build(fake_llm)
    names = {p.party_id: (p.name, p.yes) for p in digest.votes[0].parties}
    assert names["cdu"] == ("CDU/CSU", 200)
    assert names["fraktionslos"][0] == "Fraktionslos"


def test_session_sections_are_grounded_in_real_agenda_items(fake_llm: FakeLLM) -> None:
    [digest], _ = _build(fake_llm)
    assert digest.session is not None
    [section] = digest.session.sections  # the invented "A99" section is dropped
    assert section.agenda_items == ["Wohnungsbau"]
    assert section.video_url == "https://video/1.mp4"
    assert section.citations[0].url == "https://video/1.mp4#t=3"


def test_vote_llm_failure_falls_back_and_leaves_the_day_retryable() -> None:
    [digest], _ = _build(FakeLLM(fail_votes=True))
    assert digest.votes[0].short_title == "Antrag 1"
    assert digest.votes[0].topics == ["other"]
    assert digest.input_hash is None


def test_session_llm_failure_keeps_votes_and_leaves_the_day_retryable() -> None:
    [digest], _ = _build(FakeLLM(fail_session=True))
    assert digest.session is None
    assert len(digest.votes) == 2
    assert digest.input_hash is None


def test_unchanged_days_are_skipped_without_llm_calls(fake_llm: FakeLLM) -> None:
    votes = [_vote(1), _vote(2)]
    sittings = _sitting_days()
    stored = compute_input_hash(votes, sittings[date(2026, 9, 24)])
    digests, unchanged = _build(
        fake_llm,
        votes=votes,
        sittings=sittings,
        existing_hashes={"bundestag_2026-09-24": stored},
    )
    assert digests == []
    assert unchanged == 1
    assert fake_llm.calls == []


def test_vote_only_days_have_no_session(fake_llm: FakeLLM) -> None:
    digests, _ = _build(fake_llm, votes=[_vote(3, day="2026-09-23")], sittings={})
    assert [d.date for d in digests] == [date(2026, 9, 23)]
    assert digests[0].session is None
    assert digests[0].input_hash is not None


def test_agenda_ids_never_leak_into_reader_text() -> None:
    sittings = _sitting_days()
    sitting = sittings[date(2026, 9, 24)]
    refs = {"A1": sitting.agenda_items[0]}
    draft = SessionSummaryDraft(
        sections=[
            SessionSectionDraft(
                topic="housing_rent",
                headline="Mehr Wohnungen (A1)",
                summary="Die SPD fordert mehr Wohnungsbau [A1].",
                agenda_refs=["A1"],
            )
        ],
        other_topics=["Kindergeld (A3)", "[A4, A5]", "Fragestunde"],
    )
    session = session_from_draft(draft, refs, sitting)
    assert session.sections[0].headline == "Mehr Wohnungen"
    assert session.sections[0].summary == "Die SPD fordert mehr Wohnungsbau."
    assert session.other_topics == ["Kindergeld", "Fragestunde"]


def test_vote_description_takes_the_source_intro() -> None:
    assert vote_description(
        "Antrag 1\n\nThemen: Haushalt\n\nKontext: Worum es geht."
    ) == ("Worum es geht.")
    assert vote_description("Antrag ohne Kontext") is None


def test_vote_description_cuts_long_intros_at_a_sentence() -> None:
    intro = "Ein Satz. " * 400
    described = vote_description(f"Antrag\n\nKontext: {intro}")
    assert described is not None
    assert described.endswith(". …")
    assert len(described) <= 1503


def test_digests_carry_the_vote_description(fake_llm: FakeLLM) -> None:
    [digest], _ = _build(fake_llm)
    assert digest.votes[0].description == "Worum es geht."
