# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date, datetime, timezone
from typing import Any, Iterator

import pytest

from src.feed.builder import (
    DigestBuilder,
    build_digests,
    compute_input_hash,
    session_from_draft,
    vote_description,
)
from src.feed.models import DigestSessionSection
from src.feed.parliaments import PARLIAMENTS, PartyDisplay
from src.feed.prompts import (
    OpeningQuoteDraft,
    PartyPositionDraft,
    SessionSectionDraft,
    SessionSummaryDraft,
    VoteEnrichment,
    VoteEnrichmentBatch,
)
from src.feed.reader import assemble_speeches, group_sitting_days

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
        self.calls: list[type] = []

    async def __call__(self, messages: list, schema: type) -> tuple[Any, str]:
        self.calls.append(schema)
        return self._answer(messages, schema), "fake-model"

    def _answer(self, messages: list, schema: type) -> Any:
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
                        suggested_questions=[
                            "Was heißt das für mich?",
                            " ",
                            "Was heißt das für mich?",
                            "Wer war dagegen?",
                            "Was kostet das?",
                            "Eine vierte?",
                        ],
                    )
                    for ref in refs
                ]
            )
        if self.fail_session:
            raise RuntimeError("quota")
        return SessionSummaryDraft(
            sections=[
                SessionSectionDraft(
                    topics=["housing_rent"],
                    headline="Mehr Wohnungen",
                    summary="Die SPD fordert mehr Wohnungsbau.",
                    agenda_refs=["A1"],
                ),
                SessionSectionDraft(
                    topics=["health_care"],
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
    citation = section.citations[0]
    assert (citation.speaker, citation.party_id, citation.party_name) == (
        "Anna",
        "spd",
        "SPD",
    )
    assert citation.video_url == "https://video/1.mp4"


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
                topics=["housing_rent"],
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


def test_positions_keep_only_parties_and_speakers_who_spoke() -> None:
    sitting = _sitting_days()[date(2026, 9, 24)]
    refs = {"A1": sitting.agenda_items[0]}
    draft = SessionSummaryDraft(
        sections=[
            SessionSectionDraft(
                topics=["housing_rent"],
                headline="Mehr Wohnungen",
                summary="Es ging um Wohnungsbau.",
                agenda_refs=["A1"],
                positions=[
                    PartyPositionDraft(
                        party_id="SPD",
                        speakers=["anna", "Erfundene Person"],
                        position="Die SPD will mehr bauen (A1).",
                    ),
                    PartyPositionDraft(
                        party_id="spd",
                        speakers=["Anna"],
                        position="Doppelter Eintrag.",
                    ),
                    PartyPositionDraft(
                        party_id="afd",
                        speakers=["Niemand"],
                        position="Hat in dieser Debatte nicht gesprochen.",
                    ),
                ],
            )
        ],
        other_topics=[],
    )
    session = session_from_draft(draft, refs, sitting, DISPLAY)
    [position] = session.sections[0].positions
    assert position.party_id == "spd"
    assert position.party_name == "SPD"
    assert position.position == "Die SPD will mehr bauen."
    # Names link to the protocol (none known for this op-only speech), the
    # video link to the speech's moment in its video.
    assert [(s.name, s.url, s.video_link) for s in position.speakers] == [
        ("Anna", None, "https://video/1.mp4#t=3")
    ]
    assert position.speakers[0].video_url == "https://video/1.mp4"


def test_positions_merge_parties_that_share_a_fraktion() -> None:
    payloads = [
        {
            "source_item_id": sid,
            "source": "dip",
            "speech_key": f"de-21-45-{sid}-top1",
            "text": "Rede",
            "chunk_index": 0,
            "publish_date": "2026-09-24",
            "party_id": party,
            "citation_url": f"https://pdf/{sid}",
            "citation_title": sid,
            "content_hash": sid,
            "meta": {"speaker_name": name},
        }
        for sid, party, name in [("a", "cdu", "Anna"), ("b", "csu", "Bernd")]
    ]
    sitting = group_sitting_days(assemble_speeches(payloads))[date(2026, 9, 24)]
    refs = {"A1": sitting.agenda_items[0]}
    draft = SessionSummaryDraft(
        sections=[
            SessionSectionDraft(
                topics=["other"],
                headline="Debatte",
                summary="Worum es ging.",
                agenda_refs=["A1"],
                positions=[
                    PartyPositionDraft(
                        party_id="cdu", speakers=["Anna"], position="Dafür."
                    ),
                    PartyPositionDraft(
                        party_id="csu", speakers=["Bernd"], position="Auch dafür."
                    ),
                ],
            )
        ],
        other_topics=[],
    )
    session = session_from_draft(draft, refs, sitting, DISPLAY, {"csu": "cdu"})
    [position] = session.sections[0].positions
    assert position.party_name == "CDU/CSU"
    assert position.position == "Dafür."
    assert [s.name for s in position.speakers] == ["Anna", "Bernd"]


def _section_draft(**overrides: Any) -> SessionSummaryDraft:
    fields: dict[str, Any] = {
        "topics": ["housing_rent"],
        "headline": "Mehr Wohnungen",
        "summary": "Es ging um Wohnungsbau.",
        "agenda_refs": ["A1"],
    }
    fields.update(overrides)
    return SessionSummaryDraft(
        sections=[SessionSectionDraft(**fields)], other_topics=[]
    )


def _one_section(draft: SessionSummaryDraft) -> DigestSessionSection:
    sitting = _sitting_days()[date(2026, 9, 24)]
    session = session_from_draft(
        draft, {"A1": sitting.agenda_items[0]}, sitting, DISPLAY
    )
    return session.sections[0]


def test_opening_quote_is_kept_only_when_it_is_verbatim() -> None:
    section = _one_section(
        _section_draft(
            opening_quote=OpeningQuoteDraft(
                speaker="anna", quote="„Wir brauchen  mehr Wohnungen.“"
            )
        )
    )
    assert section.opening_quote is not None
    assert section.opening_quote.text == "Wir brauchen mehr Wohnungen."
    assert section.opening_quote.speaker == "Anna"
    assert section.opening_quote.party_name == "SPD"

    paraphrase = _one_section(
        _section_draft(
            opening_quote=OpeningQuoteDraft(
                speaker="Anna", quote="Wir müssen viel mehr bauen."
            )
        )
    )
    assert paraphrase.opening_quote is None

    wrong_speaker = _one_section(
        _section_draft(
            opening_quote=OpeningQuoteDraft(
                speaker="Bernd", quote="Wir brauchen mehr Wohnungen."
            )
        )
    )
    assert wrong_speaker.opening_quote is None


def test_heat_is_clamped_and_key_points_need_exactly_three() -> None:
    hot = _one_section(_section_draft(heat=9, key_points=["a", "b", "c"]))
    assert hot.heat == 5
    assert hot.key_points == ["a", "b", "c"]

    cold = _one_section(_section_draft(heat=0, key_points=["a", "b"]))
    assert cold.heat == 1
    assert cold.key_points == []

    assert _one_section(_section_draft()).heat is None


def test_debate_minutes_are_estimated_from_the_speech_text() -> None:
    # Four words of speech round up to the one-minute floor.
    assert _one_section(_section_draft()).debate_minutes == 1


def test_suggested_questions_are_deduplicated_and_capped(fake_llm: FakeLLM) -> None:
    digests, _ = _build(fake_llm)
    assert digests[0].votes[0].suggested_questions == [
        "Was heißt das für mich?",
        "Wer war dagegen?",
        "Was kostet das?",
    ]


def test_opening_quote_matches_a_speaker_copied_with_the_party_suffix() -> None:
    # The excerpts read "Anna (spd): …"; the model copies that format.
    section = _one_section(
        _section_draft(
            opening_quote=OpeningQuoteDraft(
                speaker="Anna (spd)", quote="Wir brauchen mehr Wohnungen."
            )
        )
    )
    assert section.opening_quote is not None
    assert section.opening_quote.speaker == "Anna"


def test_opening_quote_too_long_for_a_card_is_dropped() -> None:
    section = _one_section(
        _section_draft(
            opening_quote=OpeningQuoteDraft(
                speaker="Anna", quote=" ".join(["Wohnungen"] * 41)
            )
        )
    )
    assert section.opening_quote is None


def test_sections_record_the_fraktion_that_opened_the_debate() -> None:
    assert _one_section(_section_draft()).opened_by == "spd"


def test_debates_carry_up_to_two_distinct_topics_primary_first() -> None:
    sitting = _sitting_days()[date(2026, 9, 24)]
    refs = {"A1": sitting.agenda_items[0]}
    draft = SessionSummaryDraft(
        sections=[
            SessionSectionDraft(
                topics=["housing_rent", "housing_rent", "social_labor", "other"],
                headline="Mehr Wohnungen",
                summary="Es ging um Wohnungsbau.",
                agenda_refs=["A1"],
            )
        ],
        other_topics=[],
    )
    [section] = session_from_draft(draft, refs, sitting).sections
    assert section.topic == "housing_rent"
    assert section.topics == ["housing_rent", "social_labor"]


def test_a_debate_without_topics_falls_back_to_other() -> None:
    sitting = _sitting_days()[date(2026, 9, 24)]
    refs = {"A1": sitting.agenda_items[0]}
    draft = SessionSummaryDraft(
        sections=[
            SessionSectionDraft(
                topics=[], headline="X", summary="Y.", agenda_refs=["A1"]
            )
        ],
        other_topics=[],
    )
    [section] = session_from_draft(draft, refs, sitting).sections
    assert (section.topic, section.topics) == ("other", ["other"])
