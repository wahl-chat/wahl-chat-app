# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from src.generic_chat.citations import drop_unknown_citations


def test_known_citations_stay() -> None:
    text = "Die SPD stimmte zu [0], die AfD nicht [1, 2]."
    assert drop_unknown_citations(text, 3) == text


def test_an_unknown_single_citation_goes_with_its_space() -> None:
    assert drop_unknown_citations("Die SPD stimmte zu [7].", 3) == "Die SPD stimmte zu."


def test_a_list_keeps_its_known_ids() -> None:
    assert drop_unknown_citations("Zustimmung [1, 9, 2].", 3) == "Zustimmung [1, 2]."


def test_repeated_brackets() -> None:
    assert drop_unknown_citations("Zustimmung [1][9] und mehr.", 3) == "Zustimmung [1] und mehr."


def test_all_unknown_and_none() -> None:
    assert drop_unknown_citations("A [5, 6]. B [7]", 3) == "A. B"
    assert drop_unknown_citations("Keine Quelle.", 0) == "Keine Quelle."


def test_markdown_links_are_untouched() -> None:
    text = "Siehe [12](https://example.org)."
    assert drop_unknown_citations(text, 1) == text
