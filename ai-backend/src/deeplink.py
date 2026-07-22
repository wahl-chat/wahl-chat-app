# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Citation deep-link refinement (zero embeddings, never raises).

After the LLM answers, a cited op video speech can be sharpened so the user lands
on the exact passage rather than the whole speech: rewrite ``citation_url`` to
``video_uri#t={ts_start}`` so the video opens at the cited phrase
(``locate_deeplink`` / ``_speech_deeplink_url`` / ``_refine_speech_deeplinks``).

Everything here is lexical (difflib ratios + content-word overlap), takes only
already-fetched payloads, and is contractually non-raising: a malformed payload
degrades to the unrefined url, never crashing citation assembly. Source-supplied
URIs are only appended to — never fetched or executed.
"""

import difflib
import re
from typing import Optional

# Second-pass deep-link locator. A cited op speech chunk carries a
# `meta.sentence_map` (verbatim sentences + per-sentence timestamps). The locator
# matches the model's quoted text to the best sentence and rewrites the citation
# url to `video_uri#t={ts_start}` (phrase-level deep-link). Fuzzy fallback uses a
# difflib ratio; below this bar the locator opens the video at the speech start.
_DEEPLINK_FUZZY_THRESHOLD = 0.6


def locate_deeplink(quoted: str, sentence_map: list[dict], video_uri: str) -> str:
    """Map cited text to a phrase-level video deep-link (zero embeddings).

    Given the model's quoted/answer text and a matched op whole-speech chunk's
    ``meta.sentence_map`` (a list of ``{"text", "ts_start", "ts_end"}``), find the
    sentence whose text best matches and return ``f"{video_uri}#t={ts_start}"`` so
    the citation opens the video at that phrase.

    Matching (verbatim-first):
      1. Exact substring either direction (``quoted in sentence`` or
         ``sentence in quoted``) → that sentence wins immediately.
      2. Else the best ``difflib.SequenceMatcher`` ratio sentence, if it clears
         ``_DEEPLINK_FUZZY_THRESHOLD``.
      3. Else fall back to ``sentence_map[0]["ts_start"]`` — a coarse link that
         opens the video at the speech start.

    NEVER raises: an empty / None ``quoted`` or an empty / missing
    ``sentence_map`` returns ``video_uri`` unchanged (no ``#t=`` fragment), so a
    malformed payload can never crash citation assembly. The
    source-supplied ``video_uri`` is only appended to — never fetched or executed.

    Args:
        quoted: The model's quoted/answer text to locate within the speech.
        sentence_map: Verbatim sentences with ``ts_start`` timestamps.
        video_uri: The op speech's video URI (already validated at ingest).

    Returns:
        ``video_uri#t={ts_start}`` for the best sentence, or the coarse
        speech-start link, or ``video_uri`` unchanged when inputs are empty.
    """
    if not sentence_map:
        return video_uri
    # A sentence may lack ts_start on legacy/corrupt payloads; `.get` keeps the
    # "never raises" contract (a KeyError here would fail the whole party answer).
    first_ts = sentence_map[0].get("ts_start")
    q = (quoted or "").strip().lower()
    if not q:
        # No text to locate → coarse speech-start link (or bare uri if no ts).
        return f"{video_uri}#t={first_ts}" if first_ts is not None else video_uri

    best: Optional[dict] = None
    best_ratio = 0.0
    exact = False
    for sentence in sentence_map:
        text = (sentence.get("text") or "").lower()
        if not text:
            continue
        if q in text or text in q:
            best, exact = sentence, True
            break
        ratio = difflib.SequenceMatcher(None, q, text).ratio()
        if ratio > best_ratio:
            best, best_ratio = sentence, ratio

    if best is not None and (exact or best_ratio >= _DEEPLINK_FUZZY_THRESHOLD):
        ts = best.get("ts_start")
    else:
        # No sentence cleared the fuzzy bar → coarse speech-start fallback.
        ts = first_ts
    # A missing/None ts must never render as the literal "#t=None".
    return f"{video_uri}#t={ts}" if ts is not None else video_uri


# German function words / fillers to ignore when scoring query↔sentence overlap.
# Kept small and lowercase; the > 3-char length gate already drops most of them,
# but the plenary-opener words ("damen", "herren", "kollegen"…) recur in every
# speech and would otherwise dominate the overlap score.
_DEEPLINK_STOPWORDS = frozenset(
    {
        "damen",
        "herren",
        "kollegen",
        "kolleginnen",
        "präsident",
        "präsidentin",
        "sehr",
        "geehrte",
        "geehrter",
        "liebe",
        "meine",
        "unsere",
        "diese",
        "dieser",
        "dieses",
        "haben",
        "werden",
        "wird",
        "wurde",
        "worden",
        "einen",
        "eine",
        "einem",
        "einer",
        "auch",
        "aber",
        "nicht",
        "schon",
        "noch",
        "mehr",
        "sein",
        "sind",
        "dass",
        "denn",
        "dann",
        "hier",
        "damit",
        "durch",
        "über",
        "unter",
    }
)


def _content_tokens(text: str) -> set[str]:
    """Lowercase content words (> 3 chars, not a stopword) for overlap scoring."""
    return {
        w
        for w in re.findall(r"\w+", (text or "").lower())
        if len(w) > 3 and w not in _DEEPLINK_STOPWORDS
    }


def _best_sentence_ts_by_relevance(
    query: str, sentence_map: list[dict]
) -> Optional[float]:
    """Pick the ts_start of the sentence sharing the most content words with query.

    At citation-assembly time the model's answer text does not exist yet — the
    only reference text available is the (improved) RAG query, which is a
    paraphrase, not a verbatim quote, so ``locate_deeplink``'s exact/fuzzy match
    always falls back to the speech start. This lightweight lexical ranker instead
    lands the deep-link on the sentence most topically related to the question
    (zero embeddings, never raises). Returns ``None`` when nothing overlaps.
    """
    q_tokens = _content_tokens(query)
    if not q_tokens:
        return None
    best_ts: Optional[float] = None
    best_score = 0
    for sentence in sentence_map:
        score = len(q_tokens & _content_tokens(sentence.get("text") or ""))
        if score > best_score:
            best_score = score
            best_ts = sentence.get("ts_start")
    return best_ts if best_score > 0 else None


def _speech_deeplink_url(payload: dict, quoted: str) -> Optional[str]:
    """Return the citation url for a speech payload, deep-linked for op speeches.

    For an op-sourced speech (``source == "op"``) that carries a
    ``meta.sentence_map`` and ``meta.video_uri``, refine the citation to a
    phrase-level ``video_uri#t={ts_start}`` deep-link. DIP speeches (no
    ``sentence_map``) — and any op chunk missing the media payload — keep their
    stored ``citation_url`` unchanged.

    Two-stage resolution:
      1. ``locate_deeplink`` — verbatim/fuzzy match of ``quoted`` against the
         sentences (resolves the exact phrase when ``quoted`` is a real quote,
         e.g. a future post-generation refinement pass).
      2. When (1) only yields the coarse speech-start link — which is the norm
         because ``quoted`` is the paraphrased RAG query, not a verbatim quote —
         fall back to lexical query↔sentence relevance so the video still opens on
         the topically-relevant sentence rather than at 0:00.
    Never raises.
    """
    meta = payload.get("meta") or {}
    if (
        payload.get("source") == "op"
        and meta.get("sentence_map")
        and meta.get("video_uri")
    ):
        sentence_map = meta["sentence_map"]
        video_uri = meta["video_uri"]
        url = locate_deeplink(quoted, sentence_map, video_uri)
        # locate_deeplink returned the coarse speech-start link → try relevance.
        # `.get` mirrors locate_deeplink's ts_start guard so a map whose first
        # sentence lacks ts_start compares equal (both fall back to bare uri).
        first_ts = (sentence_map[0] or {}).get("ts_start")
        coarse = f"{video_uri}#t={first_ts}" if first_ts is not None else video_uri
        if url == coarse:
            ts = _best_sentence_ts_by_relevance(quoted, sentence_map)
            if ts is not None:
                return f"{video_uri}#t={ts}"
        return url
    return payload.get("citation_url")


# Inline citation markers the model emits: [N] or [N, M, ...] (0-based into sources).
_CITATION_MARKER_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _cited_claim_for_index(answer: str, idx: int) -> Optional[str]:
    """Return the sentence(s) in *answer* that actually cite source ``idx``.

    Post-generation deep-link refinement: the citation URL is first built
    BEFORE the answer exists, so the op video timestamp can only be guessed from
    the RAG query. Once the answer is in hand we can do better — feed the model's
    REAL asserted claim (the clause ending at its ``[idx]`` marker) to the video
    locator, so the deep-link lands on the sentence the answer is genuinely about
    rather than a merely query-topical one. Returns None when the source is not
    cited (keep the coarse query-based link). Never raises.
    """
    if not answer:
        return None
    claims: list[str] = []
    for match in _CITATION_MARKER_RE.finditer(answer):
        indices = {
            int(tok) for tok in match.group(1).replace(" ", "").split(",") if tok
        }
        if idx not in indices:
            continue
        # The claim is the clause ending at this marker — walk back to the prior
        # sentence terminator, then strip any other inline [..] markers.
        start = match.start()
        boundary = max(answer.rfind(sep, 0, start) for sep in (".", "!", "?", "\n"))
        clause = _CITATION_MARKER_RE.sub("", answer[boundary + 1 : start]).strip()
        if clause:
            claims.append(clause)
    return " ".join(claims) if claims else None


def _refine_speech_deeplinks(
    sources: list[dict],
    speech_refs: list[tuple[int, dict]],
    answer: str,
) -> bool:
    """Re-resolve op speech deep-links from the model's actual cited claim.

    Mutates *sources* in place: for each refinable op speech source (kept in
    *speech_refs* as ``(index_in_sources, op_payload)``) whose ``[index]`` the
    answer cites, recompute ``video_uri#t={ts}`` from the cited claim instead of
    the pre-answer RAG query, and update ``url`` / ``video_url``. Returns True when
    any URL changed (so the caller re-emits sources_ready). Never raises.
    """
    changed = False
    for idx, payload in speech_refs:
        if idx >= len(sources):
            continue
        claim = _cited_claim_for_index(answer, idx)
        if not claim:
            continue
        refined = _speech_deeplink_url(payload, claim)
        if refined and refined != sources[idx].get("url"):
            sources[idx]["url"] = refined
            if _is_video_link(refined):
                sources[idx]["video_url"] = refined
            changed = True
    return changed


def _is_video_link(url: Optional[str]) -> bool:
    """True when a URL is a playable video deep-link (``#t=`` fragment or ``.mp4``).

    Mirrors the frontend's video detection (``videoTimestampSeconds``): op speeches
    resolve to ``video_uri#t={seconds}`` direct-MP4 deep-links, while an op speech
    missing its media payload falls back to a non-video page (dbtg.tv) that must
    NOT be offered as an in-page video. Keeps ``video_url`` honest.
    """
    if not url:
        return False
    lowered = url.lower()
    # Keep in parity with the frontend isVideoUrl (web/lib/utils.ts).
    return (
        "#t=" in url
        or lowered.endswith(".mp4")
        or ".mp4#" in lowered
        or ".mp4?" in lowered
    )
