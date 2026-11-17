# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Answers to an item's suggested questions, from the item's own sources.

One call per item answers all its questions: they share the same sources,
and one call keeps the answers consistent with each other. The model sees
the sources numbered [1], [2], …: a debate's speeches, or a vote's record.
Each answer keeps only the sources it cites, renumbered from [1] in the
order it cites them, so ``SuggestedAnswer.sources`` reads like a chat
answer's sources. The rules are the chat's own (``wahlchat_common``), so the
feed and the chat answer with one voice.

A question whose answer is missing or cites nothing valid, or all of them
when the call fails, gets one immediate retry that names what was wrong. The
item keeps every valid answer; a question still without one stays ``None``
and the web shows it as a plain question. Later runs try those again, up to
``MAX_ANSWER_ATTEMPTS`` runs per item (``needs_answers``). The item itself is
never held back for it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable, Optional

from pydantic import BaseModel, Field
from wahlchat_common.answer_rules import CITATION_RULES, VOICE_RULES, language_rule

from ingestion.feed.builder import FeedBuilder, SpeechRefs, speeches_block, strip_refs
from ingestion.feed.items import content_hash
from ingestion.feed.models import (
    CANONICAL_LOCALE,
    FEED_FORMAT_VERSION,
    AnswerSource,
    FeedItem,
    LocalizedContent,
    SuggestedAnswer,
    VoteFacts,
)
from ingestion.feed.parliaments import PartyDisplay
from ingestion.feed.passages import locate
from ingestion.feed.reader import Speech

logger = logging.getLogger(__name__)

# Below the debate prompt's budget: the answers need the arguments, not
# every word.
_ANSWER_PROMPT_CHARS = 100_000
_QUESTION_REF = "F"
# "[2]", "[2, 3]" or "[2; 3]".
_CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;]\s*\d+)*)\]")
_SPEECH_LINE_RE = re.compile(r"^- \[R(\d+)\] ", re.MULTILINE)
# A question that fails this many runs stays a plain question for good.
MAX_ANSWER_ATTEMPTS = 3


class AnswerDraft(BaseModel):
    ref: str = Field(description="The question's id, e.g. 'F2'.")
    text: str = Field(
        description=(
            "The answer: 2 to 4 sentences in one paragraph, every claim cited"
            " with its source number in square brackets, e.g. [1] or [2][3]."
        )
    )


class AnswerBatch(BaseModel):
    answers: list[AnswerDraft]


ANSWER_PROMPT = """\
{voice}
Answer the questions a reader may ask about one entry of wahl.chat's daily \
overview of the {parliament}: {subject}. Use only the numbered sources \
below; they are the entry's original sources.

Rules:
{citations}\
- Answer every question, under its id, in 2 to 4 sentences in one paragraph, \
without lists or headings.
- Cite at least one source in every answer. When the sources do not answer \
a question, say so and cite what they do say about its subject.
- Attribute every position to the speaker or Fraktion that took it.
- {language}

Questions:
{questions}
{retry}
Sources:
{sources}
"""

RETRY_NOTE = """
An earlier reply to these questions was rejected:
{problems}
Answer each question above again, following the rules.
"""

GIVEN_NOTE = """
Questions already answered; stay consistent with these answers:
{answers}
"""


@dataclass
class NumberedSources:
    """An item's sources as the model sees them, and how to cite source
    ``n`` (from 1) for an answer's text."""

    block: str
    count: int
    cite: Callable[[int, str], AnswerSource]


def _speech_source(
    speech: Speech, text: str, display: dict[str, PartyDisplay]
) -> AnswerSource:
    passage = locate(text, speech, display)
    video_url = speech.video_uri
    if video_url and passage.start is not None:
        video_url = f"{video_url}#t={passage.start:g}"
    return AnswerSource(
        source=speech.citation_title or speech.speaker or "Rede",
        url=video_url or speech.protocol_page_url or speech.pdf_url,
        page=passage.page,
        source_type="parliamentary_speech",
        party_id=speech.party_id,
        snippet=passage.snippet,
        video_url=video_url,
        pdf_url=speech.pdf_url,
        document_publish_date=speech.day.isoformat(),
    )


def debate_sources(
    speeches: list[Speech], display: dict[str, PartyDisplay]
) -> NumberedSources:
    block = speeches_block(
        speeches, limit=_ANSWER_PROMPT_CHARS, refs=SpeechRefs(speeches)
    )
    return NumberedSources(
        block=_SPEECH_LINE_RE.sub(r"[\1] ", block),
        count=len(speeches),
        cite=lambda n, text: _speech_source(speeches[n - 1], text, display),
    )


def _vote_block(item: FeedItem, vote: VoteFacts) -> str:
    lines = [
        f"[1] Namentliche Abstimmung „{vote.official_title}“ am {item.date:%d.%m.%Y}"
    ]
    if vote.outcome:
        lines.append(f"Ergebnis: {vote.outcome}")
    if vote.description:
        lines.append(" ".join(vote.description.split()))
    if vote.parties:
        lines.append(
            "Stimmen je Fraktion: "
            + "; ".join(
                f"{p.name}: {p.yes} ja, {p.no} nein, {p.abstain} Enthaltungen,"
                f" {p.no_show} nicht abgegeben"
                for p in vote.parties
            )
        )
    return "\n".join(lines)


def vote_sources(item: FeedItem, vote: VoteFacts) -> NumberedSources:
    source = AnswerSource(
        source=vote.official_title,
        url=vote.citation_url,
        source_type="vote_record",
        document_publish_date=item.date.isoformat(),
    )
    return NumberedSources(
        block=_vote_block(item, vote), count=1, cite=lambda _n, _text: source
    )


def _uncited(text: str) -> str:
    text = " ".join(_CITATION_RE.sub("", text).split())
    return re.sub(r" +([.,;:!?])", r"\1", text)


def renumber(text: str, count: int) -> tuple[str, list[int]]:
    """``text`` with its citations numbered from 1 in the order it first
    cites them, and the item's source numbers they stand for. A number
    without a source is dropped."""
    cited: list[int] = []

    def replace(match: re.Match[str]) -> str:
        markers: list[str] = []
        for part in re.split(r"[,;]", match.group(1)):
            n = int(part)
            if not 1 <= n <= count:
                continue
            if n not in cited:
                cited.append(n)
            marker = f"[{cited.index(n) + 1}]"
            if marker not in markers:
                markers.append(marker)
        return "".join(markers)

    text = _CITATION_RE.sub(replace, " ".join(text.split()))
    text = re.sub(r" +([.,;:!?])", r"\1", re.sub(r" {2,}", " ", text)).strip()
    return text, cited


def unanswered(content: LocalizedContent) -> list[int]:
    """Indexes of the questions without an answer."""
    answers = content.suggested_answers
    return [
        n
        for n in range(len(content.suggested_questions))
        if n >= len(answers) or answers[n] is None
    ]


def needs_answers(item: FeedItem) -> bool:
    return (
        item.status == "published"
        and item.answer_attempts < MAX_ANSWER_ATTEMPTS
        and bool(unanswered(item.content[CANONICAL_LOCALE]))
    )


def _ref(n: int) -> str:
    return f"{_QUESTION_REF}{n + 1}"


def ground_answers(
    wanted: list[int],
    drafted: list[AnswerDraft],
    sources: NumberedSources,
) -> tuple[dict[int, SuggestedAnswer], dict[int, str]]:
    """The cited answers to the ``wanted`` questions by index, and what was
    wrong with each of the others."""
    by_ref = {d.ref.strip().strip("[]").upper(): d.text for d in drafted}
    answers: dict[int, SuggestedAnswer] = {}
    problems: dict[int, str] = {}
    for n in wanted:
        drafted_text = by_ref.get(_ref(n))
        if not drafted_text or not drafted_text.strip():
            problems[n] = f"[{_ref(n)}] had no answer."
            continue
        text, cited = renumber(strip_refs(drafted_text, _QUESTION_REF), sources.count)
        if not cited:
            problems[n] = f"[{_ref(n)}] cited none of the numbered sources."
            continue
        plain = _CITATION_RE.sub("", text)
        answers[n] = SuggestedAnswer(
            text=text, sources=[sources.cite(i, plain) for i in cited]
        )
    return answers, problems


def _subject(item: FeedItem) -> str:
    if item.debate is not None:
        return (
            f"the debate on the agenda item „{item.debate.agenda_item}“"
            f" on {item.date:%d.%m.%Y}"
        )
    assert item.vote is not None
    return f"the vote „{item.vote.official_title}“ on {item.date:%d.%m.%Y}"


def format_answer_prompt(
    parliament: str,
    item: FeedItem,
    questions: list[tuple[int, str]],
    sources: str,
    *,
    problems: Optional[list[str]] = None,
    given: Optional[list[tuple[int, str]]] = None,
) -> str:
    """``questions`` and ``given`` (answered ones) as (index, text); a retry
    names the earlier reply's ``problems``."""
    retry = ""
    if given:
        retry += GIVEN_NOTE.format(
            answers="\n".join(f"[{_ref(n)}] {_uncited(a)}" for n, a in given)
        )
    if problems:
        retry += RETRY_NOTE.format(problems="\n".join(f"- {p}" for p in problems))
    return ANSWER_PROMPT.format(
        voice=VOICE_RULES,
        parliament=parliament,
        subject=_subject(item),
        citations=CITATION_RULES,
        language=language_rule("de"),
        questions="\n".join(f"[{_ref(n)}] {q}" for n, q in questions),
        retry=retry,
        sources=sources,
    )


async def answer_item(
    builder: FeedBuilder,
    parliament_name: str,
    item: FeedItem,
    speeches: Optional[list[Speech]],
    display: dict[str, PartyDisplay],
) -> FeedItem:
    """``item`` with answers to those of its German questions that have none
    yet, and the attempt counted; as it was when there is nothing to answer,
    no source, or no time."""
    content = item.content[CANONICAL_LOCALE]
    questions = content.suggested_questions
    todo = unanswered(content)
    if not todo:
        return item
    if item.debate is not None and speeches:
        sources = debate_sources(speeches, display)
    elif item.vote is not None:
        sources = vote_sources(item, item.vote)
    else:
        return item
    answers: list[Optional[SuggestedAnswer]] = list(content.suggested_answers)
    answers += [None] * (len(questions) - len(answers))
    problems: list[str] = []
    for attempt in range(2):
        given = [(n, a.text) for n, a in enumerate(answers) if a is not None]
        prompt = format_answer_prompt(
            parliament_name,
            item,
            [(n, questions[n]) for n in todo],
            sources.block,
            problems=problems,
            given=given,
        )
        try:
            result, _ = await builder.acall(prompt, AnswerBatch)
        except TimeoutError:
            # Cut by the time budget: a later run tries again, uncounted.
            if attempt == 0:
                return item
            break
        except Exception as exc:  # noqa: BLE001 — the item stands without them
            logger.warning("Answers of %s failed: %s", item.id, exc)
            problems = ["The reply failed or could not be read."]
            continue
        found, rejected = ground_answers(todo, result.answers, sources)
        for n, answer in found.items():
            answers[n] = answer
        todo = [n for n in todo if n in rejected]
        problems = list(rejected.values())
        if not todo:
            break
    if todo:
        logger.warning(
            "No answer for %s of %s: %s", [_ref(n) for n in todo], item.id, problems
        )
    if all(a is None for a in answers):
        answers = []
    updated = content.model_copy(update={"suggested_answers": answers})
    updated.source_hash = content_hash(updated)
    return item.model_copy(
        update={
            "content": {**item.content, CANONICAL_LOCALE: updated},
            "answer_attempts": item.answer_attempts + 1,
            "format_version": FEED_FORMAT_VERSION,
        }
    )
