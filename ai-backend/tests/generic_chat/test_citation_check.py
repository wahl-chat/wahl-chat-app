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
    assert sentences[2].text.startswith("Linke: Bünger")
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


SUMMARY_ANSWER = (
    "**Kurz gesagt:**\n"
    "- **SPD**: dafür, weil es Mieter entlaste\n"
    "- **Grüne**: dagegen, weil die Dienste zu viel dürften\n"
    "\n"
    "**SPD**: Die Fraktion stimmte mit **Ja** [0]. Krings sagte, die Dienste brauchten mehr Befugnisse [4].\n"
    "\n"
    "**Grüne**: Die Fraktion lehnte ab [2]."
)
SUMMARY_HEAD = SUMMARY_ANSWER.split("\n\n**SPD**:")[0]


def test_summary_block_is_not_checked_and_survives_repair() -> None:
    sentences = cc.cited_sentences(SUMMARY_ANSWER)
    assert [s.text for s in sentences] == [
        "SPD: Die Fraktion stimmte mit Ja.",
        "Krings sagte, die Dienste brauchten mehr Befugnisse.",
        "Grüne: Die Fraktion lehnte ab.",
    ]
    verdicts = [cc.Verdict(s, sup) for s, sup in zip(sentences, [{0}, set(), {2}])]
    fixed = cc.repair(SUMMARY_ANSWER, verdicts, SOURCES)
    assert fixed.startswith(SUMMARY_HEAD + "\n\n**SPD**: Die Fraktion stimmte mit **Ja** [0]. Krings")
    assert "Befugnisse.\n\n**Grüne**: Die Fraktion lehnte ab [2]." in fixed


def test_a_citation_in_a_summary_bullet_is_checked_like_any_line() -> None:
    answer = SUMMARY_ANSWER.replace("entlaste\n", "entlaste [0]\n").replace(
        "viel dürften\n", "viel dürften [9]\n"
    )
    sentences = cc.cited_sentences(answer)
    assert sentences[0].text == "SPD: dafür, weil es Mieter entlaste"
    assert sentences[1].text == "Grüne: dagegen, weil die Dienste zu viel dürften"
    verdicts = [cc.Verdict(s, sup) for s, sup in zip(sentences, [{0}, set(), {0}, set(), {2}])]
    fixed = cc.repair(answer, verdicts, SOURCES)
    # [9] is unsupported; the bullet keeps its text and its line.
    assert "- **SPD**: dafür, weil es Mieter entlaste [0]\n" in fixed
    assert "- **Grüne**: dagegen, weil die Dienste zu viel dürften\n" in fixed
    assert fixed.startswith("**Kurz gesagt:**\n- **SPD**")
    assert cc._CITE.sub("", fixed) == cc._CITE.sub("", answer)


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
    model = TestModel(custom_output_args={"sentences": [
        {"index": 0, "supporting": [0]}, {"index": 1, "supporting": [99]}, {"index": 2, "supporting": []},
    ]})
    result = await cc.check(ANSWER, SOURCES, model=model)
    assert result.verdicts[0].supporting == {0}
    assert result.verdicts[1].supporting == set()  # an unknown id is ignored
    assert result.verdicts[2].supporting == {5}  # the found quote still counts


async def test_sentences_are_sent_numbered_without_gaps() -> None:
    prompt = cc._prompt(cc.cited_sentences(ANSWER), SOURCES)
    assert [line.split(".")[0] for line in prompt.split("Sentences:\n")[1].splitlines()] == ["0", "1", "2"]


async def test_a_reply_that_skips_or_shifts_sentences_leaves_them_unchecked() -> None:
    shifted = TestModel(custom_output_args={"sentences": [
        {"index": 1, "supporting": []}, {"index": 2, "supporting": []}, {"index": 3, "supporting": []},
    ]})
    result = await cc.check(ANSWER, SOURCES, model=shifted)
    assert [v.by for v in result.verdicts] == ["unchecked", "unchecked", "quote"]
    assert cc.repair(ANSWER, result.verdicts) == ANSWER.replace("[5, 9]", "[5]")


def test_a_quoted_law_title_settles_nothing() -> None:
    sources = [cc.Source(7, "Gesetz zur Reform des Nachrichtendienstrechts", "Gesetz zur Reform des Nachrichtendienstrechts, erste Beratung")]
    assert cc._quote_sources("Der Bundestag beschloss das „Gesetz zur Reform des Nachrichtendienstrechts“", sources) is None


def test_a_number_without_checkable_text_is_kept_and_counted() -> None:
    answer = "Am 8. September beriet der Bundestag den Entwurf [3]. Danach [4]."
    sentences = cc.cited_sentences(answer)
    stats = cc.RepairStats()
    fixed = cc.repair(answer, [cc.Verdict(sentences[0], set()), cc.Verdict(sentences[1], set())], keep=frozenset({3}), stats=stats)
    assert fixed == "Am 8. September beriet der Bundestag den Entwurf [3]. Danach."
    assert (stats.kept, stats.repointed, stats.dropped) == (1, 0, 1)
    assert cc.classify(cc.Verdict(sentences[0], set()), set(), keep=frozenset({3})) == {3: "supported"}


def test_a_named_speaker_keeps_the_citation_with_that_speaker() -> None:
    sources = [
        cc.Source(2, "Günter Krings, 2026-11-13", "…", voice="cdu", speaker="Günter Krings"),
        cc.Source(4, "Alexander Dobrindt, 2026-11-13", "gleichziehen mit Europa", voice="cdu", speaker="Alexander Dobrindt"),
    ]
    answer = "Günter Krings führte an, Deutschland müsse mit Europa gleichziehen [2]."
    verdict = cc.Verdict(cc.cited_sentences(answer)[0], {4})
    assert cc.repair(answer, [verdict], sources) == "Günter Krings führte an, Deutschland müsse mit Europa gleichziehen."


def test_a_surname_inside_a_word_names_no_one() -> None:
    sources = [
        cc.Source(0, "Ricarda Lang, 2026-11-13", "…", voice="gruene", speaker="Ricarda Lang"),
        cc.Source(1, "Abstimmung", "Outcome: angenommen", voice="record"),
        cc.Source(2, "Abstimmung 2", "angenommen nach Debatte", voice="record"),
    ]
    answer = "Der Bundestag stimmte nach langer Debatte zu [1]."
    verdict = cc.Verdict(cc.cited_sentences(answer)[0], {2})
    assert cc.repair(answer, [verdict], sources) == "Der Bundestag stimmte nach langer Debatte zu [2]."


def test_a_named_speaker_does_not_bind_a_record_citation() -> None:
    sources = [
        cc.Source(0, "Günter Krings, 2026-11-13", "…", voice="cdu", speaker="Günter Krings"),
        cc.Source(1, "Abstimmung", "…", voice="record"),
        cc.Source(2, "Abstimmung 2", "308 Ja-Stimmen", voice="record"),
    ]
    answer = "Nach der Rede von Krings fiel das Ergebnis mit 308 Ja-Stimmen aus [1]."
    verdict = cc.Verdict(cc.cited_sentences(answer)[0], {2})
    assert cc.repair(answer, [verdict], sources).endswith("aus [2].")


def test_a_markdown_link_is_no_citation() -> None:
    assert cc.cited_sentences("Siehe [2](https://example.org) dazu.") == []


def test_a_citation_behind_one_clause_is_not_swapped() -> None:
    answer = "Nach einer Anpassung Ende 2023 [27] folgte 2026 die Reform [38]."
    sentence = cc.cited_sentences(answer)[0]
    # Only [38] states the whole sentence: [27] is dropped, never moved to [38]'s clause.
    fixed = cc.repair(answer, [cc.Verdict(sentence, {38, 40})])
    assert fixed == "Nach einer Anpassung Ende 2023 folgte 2026 die Reform [38]."


async def test_a_source_date_reaches_the_check(monkeypatch: Any) -> None:
    seen: list[str] = []

    def prompt(sentences: Any, sources: Any) -> str:
        seen.append(cc._prompt(sentences, sources))
        return seen[-1]

    from src.generic_chat import stream
    from src.generic_chat.schemas import NumberedDocument
    from tests.generic_chat.conftest import make_deps

    async def check(answer: str, sources: Any) -> Any:
        prompt([], sources)
        return cc.CheckResult(verdicts=[], seconds=0.0, input_tokens=0, output_tokens=0)

    monkeypatch.setenv("GENERIC_CHAT_CITATION_CHECK", "on")
    monkeypatch.setattr(cc, "check", check)
    deps = make_deps()
    deps.sources.register({"source": "Abstimmung", "url": "https://x.de/a"})
    doc = NumberedDocument(id=0, source_type="vote_record", title="Abstimmung", date="2026-11-13", text="Total: yes 308")
    await stream._checked("Am 13. November 2026 [0].", deps, [doc])
    assert "2026-11-13 · Abstimmung" in seen[0]
