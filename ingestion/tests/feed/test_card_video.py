# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from typing import Optional

from ingestion.feed.card_video import MIN_START, choose_card_video
from ingestion.feed.models import (
    DebateFacts,
    DebateParty,
    DigestCitation,
    DigestQuote,
    DigestSpeaker,
)

VIDEO = "https://video/{}.mp4"


def _speaker(name: str, start: Optional[str] = "12.5") -> DigestSpeaker:
    url = VIDEO.format(name)
    return DigestSpeaker(
        name=name,
        video_url=url,
        video_link=f"{url}#t={start}" if start is not None else None,
    )


def _party(party_id: str, *speakers: DigestSpeaker) -> DebateParty:
    return DebateParty(
        party_id=party_id,
        party_name=party_id.upper(),
        color="#000",
        speakers=list(speakers),
    )


def _debate(
    parties: list[DebateParty],
    *,
    opener: Optional[str] = None,
    citations: Optional[list[DigestCitation]] = None,
    video_url: Optional[str] = None,
) -> DebateFacts:
    return DebateFacts(
        protocols=[],
        agenda_item="TOP 1",
        citations=citations or [],
        parties=parties,
        video_url=video_url,
        opening_quote=DigestQuote(
            text="Zitat", speaker=opener, party_id="spd", party_name="SPD"
        )
        if opener
        else None,
    )


def test_the_opening_speaker_stands_for_the_debate() -> None:
    video = choose_card_video(
        _debate(
            [_party("afd", _speaker("Dora")), _party("spd", _speaker("Anna", "40"))],
            opener="Anna",
        )
    )
    assert video is not None
    assert (video.video_url, video.start) == (VIDEO.format("Anna"), 40.0)
    assert (video.speaker, video.party_name) == ("Anna", "SPD")


def test_without_an_opener_the_seating_order_decides() -> None:
    # Stored in order of first speech; the left-most Fraktion still wins.
    video = choose_card_video(
        _debate(
            [
                _party("afd", _speaker("Dora")),
                _party("cdu", _speaker("Bernd")),
                _party("linke", _speaker("Lea")),
            ]
        )
    )
    assert video is not None
    assert video.speaker == "Lea"


def test_speakers_without_video_are_passed_over() -> None:
    silent = DigestSpeaker(name="Anna")
    video = choose_card_video(
        _debate(
            [_party("spd", silent), _party("cdu", _speaker("Bernd"))], opener="Anna"
        )
    )
    assert video is not None
    assert video.speaker == "Bernd"


def test_a_cited_speech_then_the_agenda_video_are_the_fallbacks() -> None:
    cited = DigestCitation(
        title="Rede",
        url="https://video/c.mp4#t=7.25",
        speaker="Clara",
        video_url="https://video/c.mp4",
    )
    video = choose_card_video(_debate([], citations=[cited]))
    assert video is not None
    assert (video.video_url, video.start, video.speaker) == (
        "https://video/c.mp4",
        7.25,
        "Clara",
    )

    agenda = choose_card_video(_debate([], video_url="https://video/a.mp4#t=99"))
    assert agenda is not None
    assert (agenda.video_url, agenda.start, agenda.speaker) == (
        "https://video/a.mp4",
        MIN_START,
        None,
    )


def test_a_start_too_early_or_missing_is_lifted_past_the_black_frames() -> None:
    for start in ("0", "0.2", None, "x"):
        video = choose_card_video(_debate([_party("spd", _speaker("Anna", start))]))
        assert video is not None
        assert video.start == MIN_START
    exact = choose_card_video(_debate([_party("spd", _speaker("Anna", "1.0"))]))
    assert exact is not None
    assert exact.start == 1.0


def test_a_debate_without_any_video_has_no_card_video() -> None:
    assert (
        choose_card_video(_debate([_party("spd", DigestSpeaker(name="Anna"))])) is None
    )
