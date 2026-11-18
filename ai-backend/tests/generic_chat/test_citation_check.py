# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Cited sentences, quote matching and the repair of wrong citations."""

from __future__ import annotations

from typing import Any

from pydantic_ai.models.test import TestModel

from src.generic_chat import citation_check as cc

ANSWER = (
    "Der Bundestag nahm das Gesetz an [0]. "
    "Krings sagte, die Dienste brauchten mehr Befugnisse [2][4].\n"
    "* **Linke:** Bünger nannte es „einen massiven Eingriff in die Grundrechte aller“ [5, 9]."
)
SOURCES = [
    cc.Source(0, "Abstimmung", "Outcome: angenommen"),
    cc.Source(2, "Rede Krings", "Wir brauchen moderne Befugnisse für die Dienste."),
    cc.Source(4, "Rede Dobrindt", "Sprengstoff entschärfen."),
    cc.Source(5, "Rede Bünger", "Das ist einen massiven Eingriff in die Grundrechte aller Menschen."),
]


def test_ordinals_and_dates_do_not_end_a_sentence() -> None:
    answer = "Am 13. November 2026 beschloss der Bundestag in der 21. Wahlperiode z. B. das Gesetz [0]. Danach [1]."
    assert [s.cited for s in cc.cited_sentences(answer)] == [(0,), (1,)]
    assert cc.cited_sentences(answer)[0].text.startswith("Am 13. November")


def test_sentences_carry_their_citations() -> None:
    sentences = cc.cited_sentences(ANSWER)
    assert [s.cited for s in sentences] == [(0,), (2, 4), (5, 9)]
    assert sentences[2].text.startswith("Linke:**")
    assert "[" not in sentences[1].text


async def test_a_found_quote_needs_no_model() -> None:
    result = await cc.check(ANSWER, SOURCES, model=TestModel(custom_output_args={"sentences": []}))
    quote = result.verdicts[2]
    assert quote.by == "quote" and quote.supporting == {5}


def _verdicts(supporting: list[set[int]]) -> list[cc.Verdict]:
    return [cc.Verdict(s, sup) for s, sup in zip(cc.cited_sentences(ANSWER), supporting)]


def test_repair_keeps_repoints_and_drops() -> None:
    fixed = cc.repair(ANSWER, _verdicts([{0}, {2}, {5}]))
    # [4] did not say it and [2] already cites the sentence; [9] does not exist.
    assert "Befugnisse [2]." in fixed and "Grundrechte aller“ [5, 9]." not in fixed
    assert "Grundrechte aller“ [5]." in fixed
    assert "angenommen" not in fixed and "an [0]." in fixed

    repointed = cc.repair(ANSWER, _verdicts([{0}, {4}, {5}]))
    assert "Befugnisse [4]." in repointed

    dropped = cc.repair(ANSWER, _verdicts([set(), {2, 4}, {5, 9}]))
    assert dropped.startswith("Der Bundestag nahm das Gesetz an. Krings")


def test_the_text_never_changes() -> None:
    fixed = cc.repair(ANSWER, _verdicts([set(), set(), set()]))
    assert cc._CITE.sub("", fixed) == cc._CITE.sub("", ANSWER)


def test_classify_names_every_kind() -> None:
    sentence = cc.cited_sentences(ANSWER)[1]
    known = {s.id for s in SOURCES}
    assert cc.classify(cc.Verdict(sentence, {2}), known) == {2: "supported", 4: "repointable"}
    assert cc.classify(cc.Verdict(sentence, set()), known) == {2: "unsupported", 4: "unsupported"}
    other = cc.cited_sentences(ANSWER)[2]
    assert cc.classify(cc.Verdict(other, {5}), known)[9] == "nonexistent"


def test_a_citation_never_moves_to_another_voice() -> None:
    sources = [
        cc.Source(2, "Rede Krings", "…", voice="cdu"),
        cc.Source(4, "Rede Keuter", "Counter-Hacking", voice="afd"),
        cc.Source(6, "Rede Henrichmann", "Befugnisse", voice="cdu"),
    ]
    answer = "Krings forderte Counter-Hacking [2]."
    sentence = cc.cited_sentences(answer)[0]
    voice = {s.id: s.voice for s in sources}
    assert cc.repair(answer, [cc.Verdict(sentence, {4})], sources) == "Krings forderte Counter-Hacking."
    assert cc.classify(cc.Verdict(sentence, {4}), {2, 4, 6}, voice) == {2: "other_voice"}
    assert cc.repair(answer, [cc.Verdict(sentence, {6})], sources) == "Krings forderte Counter-Hacking [6]."


async def test_the_model_names_supporting_sources(monkeypatch: Any) -> None:
    model = TestModel(custom_output_args={"sentences": [{"index": 0, "supporting": [0]}, {"index": 1, "supporting": [99]}]})
    result = await cc.check(ANSWER, SOURCES, model=model)
    assert result.verdicts[0].supporting == {0}
    assert result.verdicts[1].supporting == set()  # an unknown id is ignored
