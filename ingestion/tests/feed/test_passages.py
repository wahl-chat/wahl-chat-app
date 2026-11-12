# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from ingestion.feed.passages import best_speech, locate
from ingestion.feed.reader import Speech, SpokenSentence, assemble_speeches
from tests.feed.samples import DISPLAY, speech

PDF = "https://dserver.bundestag.de/btp/21/21045.pdf"


def _speech(text: str, sentences: list[tuple[str, float]] | None = None) -> Speech:
    [found] = assemble_speeches(
        [speech("s1", speaker="Anna", party="spd", text=text, sentences=sentences)]
    )
    return found


def _dip(text: str) -> Speech:
    found = _speech(text)
    found.video_uri = None
    found.protocol_page_url = f"{PDF}#page=12"
    return found


def test_an_aligned_speech_opens_at_the_sentence_sharing_the_most_words() -> None:
    found = _speech(
        "…",
        [
            ("Frau Präsidentin! Meine Damen und Herren!", 0.5),
            ("Die Mietpreisbremse muss verlängert werden.", 12.0),
            ("Wir brauchen mehr Wohnungen.", 20.0),
        ],
    )
    source = locate("Fordern eine Verlängerung der Mietpreisbremse.", found, DISPLAY)
    assert (source.start, source.snippet) == (
        12.0,
        "Die Mietpreisbremse muss verlängert werden.",
    )
    assert source.video_url == "https://video/s1.mp4"


def test_without_a_shared_word_the_video_opens_at_the_speech_start() -> None:
    found = _speech("…", [("Guten Morgen.", 0.5), ("Danke.", 9.0)])
    source = locate("Fordern eine Verlängerung der Mietpreisbremse.", found, DISPLAY)
    assert (source.start, source.snippet) == (0.5, None)


def test_a_speech_without_video_highlights_the_sentence_on_its_page() -> None:
    found = _dip(
        "Guten Morgen. Die Mietpreisbremse muss verlängert werden. Danke schön."
    )
    source = locate("Fordern eine Verlängerung der Mietpreisbremse.", found, DISPLAY)
    assert (source.video_url, source.start) == (None, None)
    assert (source.pdf_url, source.page) == (PDF, 12)
    assert source.snippet == "Die Mietpreisbremse muss verlängert werden."


def test_a_long_sentence_is_cut_at_a_word() -> None:
    found = _dip("Mietpreisbremse " + "lang " * 200 + "Ende.")
    snippet = locate("Mietpreisbremse", found, DISPLAY).snippet
    assert snippet is not None
    assert len(snippet) <= 300
    assert snippet.startswith("Mietpreisbremse lang")
    assert not snippet.endswith(" ")


def test_the_closest_speech_by_wording_the_earliest_on_a_tie() -> None:
    speeches = assemble_speeches(
        [
            speech("a", speaker="Anna", party="spd", text="Guten Morgen."),
            speech("b", speaker="Bernd", party="spd", text="Die Mietpreisbremse."),
            speech("c", speaker="Clara", party="spd", text="Auch Morgen."),
        ]
    )
    by_id = {s.source_item_id: s for s in speeches}
    ordered = [by_id["a"], by_id["b"], by_id["c"]]
    assert best_speech("Mietpreisbremse verlängern", ordered) is by_id["b"]
    assert best_speech("Nichts davon", ordered) is by_id["a"]
    assert best_speech("Nichts", []) is None


def test_timed_sentences_from_every_chunk_are_read_in_order_once() -> None:
    first = speech(
        "s1",
        speaker="Anna",
        party="spd",
        text="a",
        sentences=[("B.", 4.0), ("A.", 1.0)],
    )
    second = speech(
        "s1",
        speaker="Anna",
        party="spd",
        text="b",
        sentences=[("B.", 4.0), ("C.", 8.0)],
    )
    second["chunk_index"] = 1
    [found] = assemble_speeches([first, second])
    assert found.sentences == [
        SpokenSentence("A.", 1.0),
        SpokenSentence("B.", 4.0),
        SpokenSentence("C.", 8.0),
    ]


def test_the_page_is_where_the_sentence_stands_not_where_the_speech_starts() -> None:
    found = _dip("Guten Morgen. Die Mietpreisbremse muss verlängert werden.")
    asked: list[str] = []

    def page_of(sentence: str) -> int:
        asked.append(sentence)
        return 13

    found.page_of = page_of
    source = locate("Fordern eine Verlängerung der Mietpreisbremse.", found, DISPLAY)
    assert source.page == 13
    assert asked == ["Die Mietpreisbremse muss verlängert werden."]
    found.page_of = lambda _sentence: None
    assert locate("Mietpreisbremse", found, DISPLAY).page == 12
