# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Second-pass video deep-link locator — verbatim → fuzzy → speech-start fallback.

At citation time the locator picks the sentence in `meta.sentence_map` best
matching the model's quoted text and builds `video_uri#t={ts_start}`. Verbatim
substring match wins; a fuzzy near-match still resolves; a no-match falls back
to `sentence_map[0]["ts_start"]` and NEVER raises.

The citation-refinement helpers live in `src.deeplink`. The top-level
`pytest.importorskip(...)` makes this file SKIP cleanly if that module fails to
import, then runs the real assertions.
"""

from __future__ import annotations

import pytest

deeplink = pytest.importorskip(
    "src.deeplink",
    reason="src.deeplink import failed",
)

_locate = getattr(deeplink, "locate_deeplink", None)

pytestmark = pytest.mark.skipif(
    _locate is None,
    reason="locate_deeplink not present in src.deeplink",
)


_VIDEO = "https://cdn.example/7553315.mp4"
_SENTENCE_MAP = [
    {"text": "Sehr geehrte Frau Präsidentin!", "ts_start": 1.0, "ts_end": 2.8},
    {"text": "Wir stärken die Aus- und Weiterbildungsförderung.", "ts_start": 2.8, "ts_end": 6.4},
    {"text": "Das ist ein wichtiger Schritt für die Fachkräftesicherung.", "ts_start": 6.4, "ts_end": 10.2},
]


def test_verbatim_match_returns_that_sentence_ts() -> None:
    """A verbatim quote resolves to that sentence's ts_start."""
    url = _locate("Wir stärken die Aus- und Weiterbildungsförderung.", _SENTENCE_MAP, _VIDEO)
    assert url == f"{_VIDEO}#t=2.8"


def test_fuzzy_near_match_still_resolves() -> None:
    """A near (non-exact) match still resolves to the closest sentence's ts_start."""
    url = _locate("Wir staerken die Aus und Weiterbildungsfoerderung", _SENTENCE_MAP, _VIDEO)
    assert url == f"{_VIDEO}#t=2.8"


def test_no_match_falls_back_to_speech_start_and_never_raises() -> None:
    """A no-match quote falls back to sentence_map[0].ts_start without raising."""
    url = _locate("Völlig unrelated text über Verkehrspolitik", _SENTENCE_MAP, _VIDEO)
    assert url == f"{_VIDEO}#t=1.0"


def test_missing_ts_start_never_raises_and_never_emits_literal_none() -> None:
    """Regression: a sentence lacking ``ts_start`` must not raise KeyError and
    must never render as the literal ``#t=None`` (contract: "never raises")."""
    # First sentence has no ts_start; matched sentence also lacks it → bare uri.
    broken = [
        {"text": "Sehr geehrte Frau Präsidentin!"},  # no ts_start
        {"text": "Wir stärken die Weiterbildung."},  # no ts_start
    ]
    assert _locate("Wir stärken die Weiterbildung.", broken, _VIDEO) == _VIDEO
    assert _locate("", broken, _VIDEO) == _VIDEO
    # A matched sentence WITH a ts_start still resolves even if sibling lacks one.
    mixed = [
        {"text": "opener"},  # no ts_start
        {"text": "Wir stärken die Weiterbildung.", "ts_start": 4.2},
    ]
    assert _locate("Wir stärken die Weiterbildung.", mixed, _VIDEO) == f"{_VIDEO}#t=4.2"


# ---------------------------------------------------------------------------
# Query-relevance fallback (regression): at citation-assembly time only the
# paraphrased RAG query is available (not a verbatim quote), so the locator
# must still land the deep-link on the topically-relevant sentence rather than
# always the speech-start. Guards the "every video opens at 0:00" bug.
# ---------------------------------------------------------------------------

_deeplink_url = getattr(deeplink, "_speech_deeplink_url", None)

_relevance_skip = pytest.mark.skipif(
    _deeplink_url is None,
    reason="_speech_deeplink_url not present",
)

_OP_PAYLOAD = {
    "source": "op",
    "citation_url": f"{_VIDEO}#t=1.0",
    "meta": {
        "video_uri": _VIDEO,
        "sentence_map": [
            {"text": "Frau Präsidentin! Meine Damen und Herren!", "ts_start": 1.0, "ts_end": 3.0},
            {"text": "Fast jedes fünfte Kind in unserem Land lebt in Armut.", "ts_start": 45.2, "ts_end": 50.0},
            {"text": "Wir investieren in Bildung und Chancengleichheit.", "ts_start": 70.5, "ts_end": 75.0},
        ],
    },
}


@_relevance_skip
def test_query_relevance_lands_on_topical_sentence() -> None:
    """A paraphrased query lands the deep-link on the most relevant sentence's ts."""
    assert _deeplink_url(_OP_PAYLOAD, "Was sagt die Partei zu Kinderarmut und Armut von Kindern?") == f"{_VIDEO}#t=45.2"
    assert _deeplink_url(_OP_PAYLOAD, "Position zu Bildung und Chancengleichheit") == f"{_VIDEO}#t=70.5"


@_relevance_skip
def test_query_relevance_falls_back_to_speech_start_when_no_overlap() -> None:
    """No content-word overlap → coarse speech-start link (never 0:00-crash)."""
    assert _deeplink_url(_OP_PAYLOAD, "Außenpolitik Nato Verteidigung Panzer") == f"{_VIDEO}#t=1.0"


@_relevance_skip
def test_dip_speech_url_unchanged() -> None:
    """DIP speeches (no video/sentence_map) keep their stored citation_url."""
    dip = {"source": "dip", "citation_url": "https://dip.example/protocol.pdf"}
    assert _deeplink_url(dip, "irgendeine Frage") == "https://dip.example/protocol.pdf"


# ---------------------------------------------------------------------------
# Post-generation deep-link refinement: once the answer exists, re-point
# the video deep-link at the sentence the model actually cited, not the RAG query.
# ---------------------------------------------------------------------------

_cited_claim = getattr(deeplink, "_cited_claim_for_index", None)
_refine = getattr(deeplink, "_refine_speech_deeplinks", None)
_postgen_skip = pytest.mark.skipif(
    _cited_claim is None or _refine is None,
    reason="post-generation deep-link refinement not present",
)


@_postgen_skip
def test_cited_claim_extracts_clause_for_index() -> None:
    answer = (
        "Die Partei will Kinderarmut entschlossen bekämpfen [2]. "
        "Zur Bildung äußert sie sich ausführlich [0]."
    )
    assert "Kinderarmut" in _cited_claim(answer, 2)
    assert "Bildung" in _cited_claim(answer, 0)
    assert _cited_claim(answer, 5) is None  # source not cited


@_postgen_skip
def test_refine_repoints_video_deeplink_to_cited_claim() -> None:
    """The op speech at index 2 is cited for a Kinderarmut claim → its deep-link
    moves off the coarse speech-start (#t=1.0) onto the Kinderarmut sentence."""
    sources = [
        {"url": "manifesto"},
        {"url": "vote"},
        {"url": f"{_VIDEO}#t=1.0", "video_url": f"{_VIDEO}#t=1.0"},  # op speech, coarse
    ]
    speech_refs = [(2, _OP_PAYLOAD)]
    answer = "Fast jedes fünfte Kind lebt in Armut — so die Partei zur Kinderarmut [2]."

    assert _refine(sources, speech_refs, answer) is True
    assert sources[2]["url"] == f"{_VIDEO}#t=45.2"
    assert sources[2]["video_url"] == f"{_VIDEO}#t=45.2"


@_postgen_skip
def test_refine_noop_when_source_not_cited() -> None:
    """A speech the answer never cites keeps its coarse pre-answer link (no change)."""
    sources = [{"url": f"{_VIDEO}#t=1.0", "video_url": f"{_VIDEO}#t=1.0"}]
    speech_refs = [(0, _OP_PAYLOAD)]
    assert _refine(sources, speech_refs, "Eine Antwort ganz ohne Belegmarker.") is False
    assert sources[0]["url"] == f"{_VIDEO}#t=1.0"
