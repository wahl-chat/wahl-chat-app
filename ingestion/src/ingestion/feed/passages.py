# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The passage of a speech a bullet or position sentence draws on.

The model names which speeches a sentence comes from; which moment of a
speech, and which of its sentences to highlight in the protocol, is decided
here, by the content words (failing that, the word stems) the two share. A paraphrase never matches a
transcript verbatim, so overlap is the measure, and the model never writes a
timestamp or a quote that a reader would then be sent to.
"""

from __future__ import annotations

import re
from typing import Optional

from ingestion.feed.models import SpeechSource
from ingestion.feed.parliaments import PartyDisplay, party_display_for
from ingestion.feed.reader import SpokenSentence, Speech
from wahlchat_common.content_words import content_words

# Long enough to find the sentence on the PDF page, short enough that a
# highlight does not run over half the page.
_SNIPPET_CHARS = 300
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[„\"A-ZÄÖÜ])")
_PAGE_RE = re.compile(r"#page=(\d+)")
# German compounds and inflections ("Diätenaussetzung" for "Diäten
# aussetzen") rarely share a whole word with a summary of them, but often
# their first letters.
_STEM_CHARS = 6

Score = tuple[int, int]


def _stems(words: set[str]) -> set[str]:
    return {w[:_STEM_CHARS] for w in words}


def _overlap(words: set[str], other: str) -> Score:
    """Shared words first; shared stems only break a tie or stand in when no
    word is shared, since on their own they favour common words ("Reform",
    "Hersteller") over the specific one."""
    found = content_words(other)
    return len(words & found), len(_stems(words) & _stems(found))


def _best_sentence(text: str, sentences: list[str]) -> Optional[int]:
    """Index of the sentence sharing the most with ``text``; the earliest wins
    a tie. None when no sentence shares a word or a stem."""
    words = content_words(text)
    best, best_score = None, (0, 0)
    for index, sentence in enumerate(sentences):
        score = _overlap(words, sentence)
        if score > best_score:
            best, best_score = index, score
    return best


def _written_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END_RE.split(" ".join(text.split())) if s]


def _snippet(sentence: str) -> str:
    if len(sentence) <= _SNIPPET_CHARS:
        return sentence
    return sentence[:_SNIPPET_CHARS].rsplit(" ", 1)[0]


def _page(url: Optional[str]) -> Optional[int]:
    match = _PAGE_RE.search(url or "")
    return int(match.group(1)) if match else None


def best_speech(text: str, speeches: list[Speech]) -> Optional[Speech]:
    """The speech whose text shares the most with ``text``, the earliest on a
    tie."""
    words = content_words(text)
    scored = [(_overlap(words, s.text), -i, s) for i, s in enumerate(speeches)]
    best = max(scored, default=None, key=lambda entry: entry[:2])
    return best[2] if best else None


def locate(text: str, speech: Speech, display: dict[str, PartyDisplay]) -> SpeechSource:
    """Where in ``speech`` the sentence ``text`` comes from.

    An aligned speech is matched sentence by sentence against its timed
    transcript, so the video starts at that sentence; a speech without one
    against its own text. With no overlap at all, the source is the speech
    from its start, with nothing highlighted.
    """
    timed: list[SpokenSentence] = speech.sentences
    sentence: Optional[str] = None
    start: Optional[float] = None
    if timed:
        index = _best_sentence(text, [s.text for s in timed])
        start = timed[0].ts_start
        if index is not None:
            sentence, start = timed[index].text, timed[index].ts_start
    else:
        written = _written_sentences(speech.text)
        index = _best_sentence(text, written)
        sentence = written[index] if index is not None else None
    party = party_display_for(speech.party_id, display)
    page = _page(speech.protocol_page_url)
    if sentence and speech.page_of is not None:
        # A long speech runs over pages; the viewer highlights on one.
        page = speech.page_of(sentence) or page
    return SpeechSource(
        speaker=speech.speaker or "Unbekannt",
        party_id=speech.party_id,
        party_name=party.name,
        video_url=speech.video_uri,
        start=start if speech.video_uri else None,
        pdf_url=speech.pdf_url,
        page=page,
        snippet=_snippet(sentence) if sentence else None,
    )
