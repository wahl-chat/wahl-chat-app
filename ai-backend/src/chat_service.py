# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Chat service module — SSE streaming (emit→yield adaptation).

All V1 socket_emit() calls are converted to yield statements emitting Vercel AI SDK
data-stream protocol events:
  f  — message frame init
  0  — text delta (token chunk)
  8  — data annotation (sources_ready, responding_parties, party_complete, etc.)
  e  — step finish
  d  — final summary
  [DONE] — stream end

Multi-party streaming: SERIALIZED (one party at a time).
True concurrent multiplexed SSE would require an asyncio.Queue
dispatcher — deferred for now.

Session state: STATELESS. The client sends full chat_history per request.
No server-side session store.
"""

import asyncio
import difflib
import json
import re
import time
from datetime import datetime
import logging
import random
import uuid
from typing import AsyncGenerator, List, Dict, Optional, Union, cast

import openai
from fastapi import Request as FastAPIRequest
from langchain_core.messages import BaseMessageChunk
from langchain_core.documents import Document

from src.chatbot_async import (
    generate_chat_title_and_chick_replies,
    get_question_targets_and_type,
    generate_improvement_rag_query,
    generate_streaming_chatbot_response,
    generate_streaming_chatbot_comparing_response,
    build_vote_documents,
)
from src.ingestion.retrieve import retrieve, retrieve_two_pass
from src.ingestion.connectors.abgeordnetenwatch.legislature_config import (
    term_window_for_context,
)
from src.firebase_service import (
    aget_cached_answers_for_party,
    aget_context_by_id,
    aget_parties_for_context,
    aget_proposed_questions_for_party,
    awrite_cached_answer_for_party,
)
from src.models.chat import CachedResponse, GroupChatSession, Message, Role
from src.models.dtos import (
    SourcesDto,
    PartyResponseCompleteDto,
    QuickRepliesAndTitleDto,
    Status,
    StatusIndicator,
)
from src.models.context import ContextParty
from src.models.party import WAHL_CHAT_PARTY
from src.vector_store_helper import embed
from src.utils import (
    build_chat_history_string,
    get_chat_history_hash_key,
    sanitize_references,
)

MAX_RESPONSE_CHUNK_LENGTH = 10  # preserved from V1 for cached-response replay

# Minimum cosine similarity for a result to be included in chat retrieval.
# V1 used 0.5; the collection uses text-embedding-3-large (cosine space, range [0,1]).
# Empty results are gracefully tolerated — the LLM receives "Keine relevanten
# Informationen" for that source type, producing a valid (possibly empty) context.
_CHAT_SCORE_THRESHOLD = 0.5

# Two-pass temporal retrieval (Phase 09, decisions D1/D4).
# When a term window resolves for the chat context (term_window_for_context),
# each source is retrieved in TWO passes:
#   - current pass  : publish_date ∈ [term_start, term_end], FLAT, keeps the
#                     EXISTING per-source current limits (no regression on the
#                     current record). Uses _CHAT_SCORE_THRESHOLD (0.5).
#   - historic pass : publish_date < term_start, gated by a HIGH threshold so
#                     only strongly on-topic history returns, and kept small
#                     (context-only, D4 + Claude's-discretion budget split).
# The two buckets are merged CURRENT-FIRST, HISTORIC-AFTER into a single
# combined grounding; sources[] are built in the IDENTICAL bucket-then-source
# order so [N] citations stay aligned with combined_docs. Per-section rendering
# ("Historically, SPD …") is DEFERRED to the response-structuring plan.
_HISTORIC_SCORE_THRESHOLD = 0.6
_HISTORIC_LIMITS = {"vote": 2, "manifesto": 2, "speech": 1}

# Current-bucket per-source budgets (Phase 10, D1/D4 — the "speeches overcrowd
# the answer" fix). Grounding is ordered manifesto → vote → speech, so speeches
# rank LAST and are budget-capped, BUT expand adaptively when official data
# (votes + manifesto) is sparse so vote-sparse contexts (e.g. Rheinland-Pfalz =
# 5 recorded votes for a whole term) still produce a substantive answer.
#   - manifesto / vote: unchanged from the pre-Phase-10 caps.
#   - speech: fetched at the FALLBACK ceiling, then trimmed to the normal cap
#     ONLY when official data is present (see _official_coverage + the adaptive
#     trim in fetch_party_response_stream / process_party). When official data is
#     sparse the fetched-at-ceiling speeches are kept so the answer isn't starved.
_CURRENT_VOTE_LIMIT = 5
_CURRENT_MANIFESTO_LIMIT = 4
_CURRENT_SPEECH_LIMIT = 2          # normal cap (reduced from 3 per D4 — ranked last)
_CURRENT_SPEECH_FALLBACK = 5       # adaptive ceiling when official data is sparse

# Second-pass deep-link locator (D-02b). A cited op speech chunk carries a
# `meta.sentence_map` (verbatim sentences + per-sentence timestamps). The locator
# matches the model's quoted text to the best sentence and rewrites the citation
# url to `video_uri#t={ts_start}` (phrase-level deep-link). Fuzzy fallback uses a
# difflib ratio; below this bar the locator opens the video at the speech start.
_DEEPLINK_FUZZY_THRESHOLD = 0.6


def locate_deeplink(quoted: str, sentence_map: list[dict], video_uri: str) -> str:
    """Map cited text to a phrase-level video deep-link (D-02b, zero embeddings).

    Given the model's quoted/answer text and a matched op whole-speech chunk's
    ``meta.sentence_map`` (a list of ``{"text", "ts_start", "ts_end"}``), find the
    sentence whose text best matches and return ``f"{video_uri}#t={ts_start}"`` so
    the citation opens the video at that phrase.

    Matching (verbatim-first, per RESEARCH Q4):
      1. Exact substring either direction (``quoted in sentence`` or
         ``sentence in quoted``) → that sentence wins immediately.
      2. Else the best ``difflib.SequenceMatcher`` ratio sentence, if it clears
         ``_DEEPLINK_FUZZY_THRESHOLD``.
      3. Else fall back to ``sentence_map[0]["ts_start"]`` — a coarse link that
         opens the video at the speech start.

    NEVER raises: an empty / None ``quoted`` or an empty / missing
    ``sentence_map`` returns ``video_uri`` unchanged (no ``#t=`` fragment), so a
    malformed payload can never crash citation assembly (threat T-11-20). The
    source-supplied ``video_uri`` is only appended to — never fetched or executed
    (threat T-11-19).

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
    phrase-level ``video_uri#t={ts_start}`` deep-link (D-02b). DIP speeches (no
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


# ---------------------------------------------------------------------------
# Payload → numbered-Document builders (shared by the single-party and
# comparison paths). Speech/manifesto payloads become Document objects so they
# flow through the numbered-Document machinery (get_rag_context /
# build_document_string_for_context) and the LLM cites them as clean [N] integer
# IDs. Kept at module level (not re-defined per call) so both paths stay in sync.
# ---------------------------------------------------------------------------
def _mk_manifesto_docs(payloads: list[dict]) -> list[Document]:
    return [
        Document(
            page_content=(p.get("text") or ""),
            metadata={
                "document_name": p.get("citation_title"),
                "document_publish_date": p.get("publish_date"),
                "url": p.get("citation_url"),
                "page": (p.get("meta") or {}).get("page_start"),
                "source_document": p.get("citation_title"),
                "authority_tier": p.get("authority_tier"),
            },
        )
        for p in payloads
    ]


def _mk_speech_docs(payloads: list[dict], improved_rag_query: str) -> list[Document]:
    # op speeches carry a video deep-link (meta.sentence_map + video_uri);
    # rewrite their url to video_uri#t={ts_start} (D-02b). DIP unchanged.
    return [
        Document(
            page_content=(p.get("text") or ""),
            metadata={
                "document_name": p.get("citation_title"),
                "document_publish_date": p.get("publish_date"),
                "url": _speech_deeplink_url(p, improved_rag_query),
                "page": 1,
                "source_document": p.get("citation_title"),
                "authority_tier": p.get("authority_tier"),
            },
        )
        for p in payloads
    ]


# Inline citation markers the model emits: [N] or [N, M, ...] (0-based into sources).
_CITATION_MARKER_RE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def _cited_claim_for_index(answer: str, idx: int) -> Optional[str]:
    """Return the sentence(s) in *answer* that actually cite source ``idx``.

    Post-generation deep-link refinement (D-02b): the citation URL is first built
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
        indices = {int(tok) for tok in match.group(1).replace(" ", "").split(",") if tok}
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
    """Re-resolve op speech deep-links from the model's actual cited claim (D-02b).

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


# A word this long is almost certainly a German compound the PDF will hyphenate at
# a column line-break ("Weiterbildungs-\nförderung"), which breaks a native
# `#search=` substring match — so a snippet window is penalised for containing one.
_HYPHENATION_PRONE_LEN = 14


def _search_snippet(
    source_text: str, claim: str, *, max_words: int = 8
) -> Optional[str]:
    """Pick a short verbatim phrase from *source_text* to drive a PDF ``#search=``.

    Best-effort in-document highlight: the native browser PDF viewer jumps to and
    highlights the first occurrence of a ``#search=`` fragment. To make that land on
    the CITED passage (not a merely topical one, and never the model's paraphrased
    answer text — which is not verbatim in the PDF), lexically match the model's
    asserted *claim* against the source chunk's own sentences, take the best sentence,
    then return the contiguous window (≤ ``max_words``) that best balances two forces:

      * **distinctiveness** — maximise shared content words with the claim, so the
        phrase is specific enough to (a) land on the cited passage, not a merely
        topical one, and (b) not collide with a different speaker's identical wording
        earlier in a long Plenarprotokoll (the DIP grounding risk);
      * **matchability** — avoid very long compound words, which the PDF hyphenates at
        column line-breaks and which then defeat the native viewer's substring match.

    Whitespace and soft-hyphens are normalised. Returns None when nothing usefully
    overlaps, so the caller omits the fragment and the page anchor (AW) / page 1 (DIP)
    is left unchanged. Never raises.
    """
    if not source_text or not claim:
        return None
    claim_tokens = _content_tokens(claim)
    if not claim_tokens:
        return None
    # Best-matching source sentence (shared content words with the cited claim).
    best_sentence = ""
    best_score = 0
    for sentence in re.split(r"(?<=[.!?])\s+", source_text):
        score = len(claim_tokens & _content_tokens(sentence))
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if best_score == 0:
        return None
    norm = re.sub(r"\s+", " ", best_sentence.replace("­", "")).strip()
    words = norm.split(" ")

    def _window_score(window: list[str]) -> int:
        # Distinctiveness (weighted heaviest) minus a per-long-word matchability
        # penalty. Longer overall phrase breaks ties toward the more specific span.
        overlap = len(claim_tokens & _content_tokens(" ".join(window)))
        hyphenation_prone = sum(
            1 for w in window if len(w.strip(".,;:!?»«\"'()")) > _HYPHENATION_PRONE_LEN
        )
        return overlap * 4 - hyphenation_prone * 3 + len(window)

    if len(words) <= max_words:
        return norm or None
    best_window = words[:max_words]
    best_win_score = _window_score(best_window)
    for start in range(1, len(words) - max_words + 1):
        window = words[start : start + max_words]
        score = _window_score(window)
        if score > best_win_score:
            best_win_score = score
            best_window = window
    return " ".join(best_window) or None


def _refine_pdf_highlights(
    sources: list[dict],
    highlight_refs: list[tuple[int, str]],
    answer: str,
) -> bool:
    """Attach a best-effort ``#search=`` snippet to each cited PDF-backed source.

    Mutates *sources* in place: for each source recorded in *highlight_refs* as
    ``(index_in_sources, verbatim_chunk_text)`` whose ``[index]`` the answer cites,
    derive a short verbatim phrase from the passage the citation is about (see
    ``_search_snippet``) and store it as ``sources[idx]["snippet"]``. The frontend
    appends it as a native-viewer ``#search=`` fragment to jump to / highlight the
    cited text — AW manifestos keep their exact ``#page=`` anchor as well, while
    XML-ingested DIP speeches (no page map) rely on the snippet alone. Returns True
    when any snippet was set (so the caller re-emits sources_ready). Never raises.
    """
    changed = False
    for idx, source_text in highlight_refs:
        if idx >= len(sources):
            continue
        claim = _cited_claim_for_index(answer, idx)
        if not claim:
            continue
        snippet = _search_snippet(source_text, claim)
        if snippet and snippet != sources[idx].get("snippet"):
            sources[idx]["snippet"] = snippet
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


def _speech_attribution(payload: dict) -> dict:
    """Surface ODbL/Bundestag attribution from an op speech's meta (Q8).

    Returns a dict with ``creator`` / ``license`` / ``source_data`` when present
    (op speeches), else an empty dict (DIP speeches carry no such meta). The app
    CAN render these; frontend rendering itself is out of scope this phase.
    """
    meta = payload.get("meta") or {}
    attribution = {
        key: meta.get(key)
        for key in ("creator", "license", "source_data")
        if meta.get(key)
    }
    return attribution


def _official_coverage(
    vote_docs_current: list, manifesto_current: list
) -> tuple[bool, bool]:
    """Report whether "official" grounding is absent in the CURRENT bucket.

    Returns ``(votes_absent, manifesto_absent)`` where:
      - ``votes_absent == (len(vote_docs_current) == 0)``, computed from the
        PARTICIPATION-FILTERED vote DOCUMENTS (``build_vote_documents`` output —
        the votes that actually reach the answer), NOT the raw vote payloads, so
        the signal is epistemically honest about grounding coverage.
      - ``manifesto_absent == (len(manifesto_current) == 0)``.

    ``official_sparse`` is the disjunction ``votes_absent or manifesto_absent``;
    this helper returns the two booleans and leaves the disjunction to callers.
    Task 10-01 consumes it to drive the adaptive speech trim; plan 10-02 consumes
    it to drive the SC5 coverage-transparency line.
    """
    votes_absent = len(vote_docs_current) == 0
    manifesto_absent = len(manifesto_current) == 0
    return votes_absent, manifesto_absent


def _has_historic_docs(
    docs_by_party: Optional[Dict[str, List[Document]]],
    term_window: Optional[tuple[datetime, datetime]],
) -> bool:
    """Best-effort D3 signal for the COMPARISON path.

    The comparison grounding (process_party) merges current+historic per party into
    a single per-party list WITHOUT a per-doc historic marker, so re-derive the
    signal from ``document_publish_date`` vs the window start: a doc that predates
    ``term_start`` came from a historic two-pass bucket. Returns False when no window
    resolved (single-pass contexts have no historic bucket) or when dates are
    unparseable — never fabricating a historic section the grounding can't support.

    The single-party path does NOT use this helper — there the raw historic payload
    buckets are still in scope (see ``has_historic`` in fetch_party_response_stream).
    """
    if term_window is None or not docs_by_party:
        return False
    term_start = term_window[0]
    for docs in docs_by_party.values():
        for doc in docs:
            raw = doc.metadata.get("document_publish_date")
            if not raw:
                continue
            try:
                published = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                continue
            # Align tz-awareness with term_start before comparing.
            if published.tzinfo is None and term_start.tzinfo is not None:
                published = published.replace(tzinfo=term_start.tzinfo)
            elif published.tzinfo is not None and term_start.tzinfo is None:
                published = published.replace(tzinfo=None)
            if published < term_start:
                return True
    return False

# Per-stream wall-clock budget (seconds).
# Prevents a wedged LLM stream from keeping the SSE connection open forever —
# the 15s heartbeat keeps the wire alive so without this budget, a hung model
# call would burn tokens indefinitely.
# 180s is generous for even the slowest multi-party comparison answer.
_CHAT_STREAM_BUDGET_S = 180

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: data-stream event framing
# ---------------------------------------------------------------------------
def _sse(part: object) -> str:
    """Serialize one AI SDK v5 UI-message-stream part as an SSE event.

    v5 framing: ``data: <json>\n\n`` where <json> is a part object with a
    ``type`` discriminator (start, text-delta, data-<name>, finish, ...).
    """
    return f"data: {json.dumps(part)}\n\n"


def _frame(event_type: str, payload: object) -> str:
    """Map a legacy event code to AI SDK v5 UI-message-stream part(s).

    The v1 hand-rolled wire codes (f/0/8/e/d) are translated to the real v5
    UI-message-stream parts so ``@ai-sdk/react`` useChat can parse the stream.
    All V1 named chat events (type '8') are carried verbatim inside a single
    custom ``data-chat_event`` part (the frontend switches on ``data.type``).
    """
    if event_type == "f":
        msg_id = payload.get("messageId") if isinstance(payload, dict) else None
        # message start + open the first step
        return _sse({"type": "start", "messageId": msg_id}) + _sse(
            {"type": "start-step"}
        )
    if event_type == "8":
        return _sse({"type": "data-chat_event", "data": payload})
    if event_type == "e":
        return _sse({"type": "finish-step"})
    if event_type == "d":
        return _sse({"type": "finish"})
    if event_type == "0":
        # Bare text delta without an explicit text block (fallback id). Callers
        # that stream a party answer should bracket with _text_start/_text_end.
        return _sse({"type": "text-delta", "id": "txt", "delta": payload})
    # Unknown legacy code — surface as a generic data part rather than break.
    return _sse({"type": "data-chat_event", "data": payload})


def _text_start(text_id: str) -> str:
    """Open a v5 text block for one party answer."""
    return _sse({"type": "text-start", "id": text_id})


def _text_delta(text_id: str, token: str) -> str:
    """Emit one v5 text-delta token within an open text block."""
    return _sse({"type": "text-delta", "id": text_id, "delta": token})


def _text_end(text_id: str) -> str:
    """Close a v5 text block."""
    return _sse({"type": "text-end", "id": text_id})


def _party_chunk(session_id: str, party_id: str, chunk: str) -> str:
    """Emit one incremental answer chunk as a `party_chunk` data annotation.

    The frontend renders the visible chat from the Zustand store, not from
    useChat's internal `messages`. The store appends a party's answer live via
    `mergeStreamingChunkPayloadForMessage`, which keys on `party_chunk` events
    carrying `chunk_content` (the V1 `party_response_chunk_ready` contract).
    The v5 `text-delta` parts feed useChat's (unrendered) message state only, so
    without this companion event the answer only appears at `party_complete` —
    as one block. Emitting both keeps useChat's stream valid AND streams to the UI.
    """
    return _frame(
        "8",
        {
            "type": "party_chunk",
            "session_id": session_id,
            "party_id": party_id,
            "chunk_content": chunk,
        },
    )


# ---------------------------------------------------------------------------
# Helper: SSE idle keep-alive (heartbeat / proxy survival)
# ---------------------------------------------------------------------------
# StreamingResponse (chosen to avoid EventSourceResponse double-framing) has no
# automatic keep-alive. During idle gaps — chiefly the wait before the first LLM
# token while sources are retrieved — a silent connection can be dropped by
# corporate proxies on an idle timeout, the exact failure that motivated the move
# off WebSockets. This wrapper interleaves an SSE comment line (": ...\n\n", which
# Vercel-AI / EventSource parsers ignore) whenever the wrapped generator produces
# nothing for `interval` seconds, keeping the connection warm without affecting
# the data stream.
async def with_heartbeat(
    agen: AsyncGenerator[str, None], interval: float = 15.0
) -> AsyncGenerator[str, None]:
    aiter = agen.__aiter__()
    pending: Optional[asyncio.Task] = None
    try:
        while True:
            if pending is None:
                pending = asyncio.ensure_future(aiter.__anext__())
            done, _ = await asyncio.wait({pending}, timeout=interval)
            if pending in done:
                try:
                    item = pending.result()
                except StopAsyncIteration:
                    return
                finally:
                    pending = None
                yield item
            else:
                # No chunk within `interval`; keep the same pending task and ping.
                yield ": keep-alive\n\n"
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
        await agen.aclose()


# ---------------------------------------------------------------------------
# Cached-response yielder (replaces emit_cached_party_response)
# ---------------------------------------------------------------------------
async def yield_cached_party_response(
    party: ContextParty,
    group_chat_session: GroupChatSession,
    cached_response: CachedResponse,
) -> AsyncGenerator[str, None]:
    """Yield SSE events for a cached party response (simulated streaming).

    Replaces V1's emit_cached_party_response which called socket_emit().
    """
    await asyncio.sleep(1)

    sources_dto = SourcesDto(
        session_id=group_chat_session.session_id,
        sources=cached_response.sources,
        party_id=party.party_id,
        rag_query=cached_response.rag_query,
    )
    # 8: data annotation — sources_ready (replaces V1 socket_emit("sources_ready", ...))
    yield _frame("8", {"type": "sources_ready", **sources_dto.model_dump()})

    full_response = cached_response.content
    message_id = str(uuid.uuid4())
    # v5 text block — id ties the deltas to one assistant text part.
    yield _text_start(message_id)
    chunk_index = 0
    for i in range(0, len(full_response), MAX_RESPONSE_CHUNK_LENGTH):
        chunk = full_response[i : i + MAX_RESPONSE_CHUNK_LENGTH]
        if chunk_index > 0:
            await asyncio.sleep(0.025)
        yield _text_delta(message_id, chunk)
        yield _party_chunk(group_chat_session.session_id, party.party_id, chunk)
        chunk_index += 1
    yield _text_end(message_id)

    chatbot_message = Message(
        id=message_id,
        role="assistant",
        content=full_response,
        sources=cached_response.sources,
        party_id=party.party_id,
        current_chat_title=group_chat_session.title,
        quick_replies=[],
        rag_query=cached_response.rag_query,
    )
    group_chat_session.chat_history.append(chatbot_message)

    party_response_complete_dto = PartyResponseCompleteDto(
        session_id=group_chat_session.session_id,
        party_id=party.party_id,
        complete_message=full_response,
        message_id=message_id,
        status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
    )
    # 8: data annotation — party_complete (replaces V1 socket_emit("party_response_complete", ...))
    yield _frame(
        "8",
        {"type": "party_complete", **party_response_complete_dto.model_dump()},
    )
    logger.info(
        f"Cached party response for {party.party_id} yielded "
        f"(message_id={message_id})"
    )


# ---------------------------------------------------------------------------
# Single-party response stream (replaces fetch_and_emit_party_response)
# ---------------------------------------------------------------------------
async def fetch_party_response_stream(
    party: ContextParty,
    conversation_history_str: str,
    question_for_party: str,
    group_chat_session: GroupChatSession,
    all_available_parties: List[ContextParty],
    use_premium_llms: bool,
    is_proposed_question: bool = False,
    is_cacheable_chat: bool = True,
    relevant_docs: Optional[Union[List[Document], Dict[str, List[Document]]]] = None,
    parties_being_compared: Optional[List[ContextParty]] = None,
    is_comparing_question: bool = False,
    improved_rag_query_list: List[str] = [],
    region_path: Optional[List[str]] = None,
    legislature_period_id: Optional[int] = None,
    election_level: Optional[str] = None,
    term_window: Optional[tuple[datetime, datetime]] = None,
) -> AsyncGenerator[str, None]:
    """Yield SSE events for a single party's RAG response.

    Replaces V1's fetch_and_emit_party_response (which emitted to socketio).
    Multi-party callers iterate parties SEQUENTIALLY.
    """
    relevant_docs_list: Optional[List[Document]] = None
    relevant_docs_dict: Optional[Dict[str, List[Document]]] = None
    cache_key: Optional[str] = None
    cached_answer_to_emit: Optional[CachedResponse] = None
    cache_conversation_history_str = build_chat_history_string(
        group_chat_session.chat_history, all_available_parties
    )
    full_response: Optional[BaseMessageChunk] = None
    sources: list = []
    # (index_in_sources, op_payload) for op speeches whose video deep-link can be
    # refined from the model's actual cited claim once the answer exists (D-02b).
    speech_refs: list[tuple[int, dict]] = []
    # (index_in_sources, verbatim_chunk_text) for PDF-backed sources (manifestos +
    # speeches) that can gain a best-effort `#search=` highlight from the cited claim.
    highlight_refs: list[tuple[int, str]] = []

    try:
        # Caching logic preserved from V1
        if is_proposed_question or is_cacheable_chat:
            if is_proposed_question:
                cache_key = question_for_party
            else:
                cache_key = get_chat_history_hash_key(cache_conversation_history_str)
            logger.debug(
                f"Checking cache for party {party.party_id} with key {cache_key}"
            )
            existing_cached_answers: List[CachedResponse] = (
                await aget_cached_answers_for_party(party.party_id, cache_key)
            )
            cached_answer_limit = 1
            possible_answers: list = (
                existing_cached_answers + [None]
                if len(existing_cached_answers) < cached_answer_limit
                else existing_cached_answers
            )
            cached_answer_to_emit = random.choice(possible_answers)

        if cached_answer_to_emit is not None:
            logger.info(
                f"Serving cached response for party {party.party_id}"
            )
            async for event in yield_cached_party_response(
                party, group_chat_session, cached_answer_to_emit
            ):
                yield event
            return

        # RAG retrieval
        if not is_comparing_question:
            improved_rag_query = await generate_improvement_rag_query(
                party,
                conversation_history_str,
                question_for_party,
                context_id=group_chat_session.context_id,
            )
            # Embed the rag query ONCE and reuse the vector for all three
            # source retrievals (vote, manifesto, speech). This avoids three
            # separate OpenAI embed API calls for the same query string.
            # The V1 identify_relevant_docs_with_llm_based_reranking call that
            # previously sat here queried the EMPTY all_parties_dev / context
            # collection — it was producing zero documents and wasting an embed.
            # It is replaced with a no-op empty list; the single-store sources
            # (manifesto, speech, vote) below are the canonical doc sources.
            rag_query_vector = await embed.aembed_query(improved_rag_query)
            relevant_docs_list = []  # V1 legacy slot — now always empty (typed at decl)
            improved_rag_query_list = [improved_rag_query]

            # Run all three per-source retrieve() calls concurrently via
            # asyncio.gather so they execute in parallel (Qdrant supports concurrent
            # reads). return_exceptions=True ensures a failure in one source never
            # kills the others; exceptions are coerced to [] with a warning below.
            # The WAHL_CHAT_PARTY (wahl-chat assistant) has no party_ids and no
            # party_manifesto / parliamentary_speech data — skip all three sources
            # for it (it will have empty payloads and an empty answer context).
            async def _safe_retrieve(*args, **kwargs) -> list[dict]:  # type: ignore[no-untyped-def]
                """Wrap retrieve() so a failure returns [] rather than raising."""
                try:
                    # This wrapper only ever calls retrieve() with_scores=False, so the
                    # result is a list[dict]; narrow retrieve()'s union return.
                    return cast(
                        list[dict], await asyncio.to_thread(retrieve, *args, **kwargs)
                    )
                except Exception as _err:  # noqa: BLE001
                    logger.warning(
                        "retrieve() failed (source=%s party=%s): %s",
                        kwargs.get("source_type"),
                        kwargs.get("party_id") or kwargs.get("party_ids_contains"),
                        _err,
                        exc_info=True,
                    )
                    return []

            async def _safe_two_pass(**kwargs) -> dict[str, list[dict]]:  # type: ignore[no-untyped-def]
                """Wrap retrieve_two_pass() so a failure returns empty buckets.

                Mirrors _safe_retrieve but for the temporal two-pass mode: on any
                exception it returns ``{"current": [], "historic": []}`` so a single
                source failure never kills the other two nor the whole answer.
                """
                try:
                    return await asyncio.to_thread(
                        retrieve_two_pass, improved_rag_query, **kwargs
                    )
                except Exception as _err:  # noqa: BLE001
                    logger.warning(
                        "retrieve_two_pass() failed (source=%s party=%s): %s",
                        kwargs.get("source_type"),
                        kwargs.get("party_id") or kwargs.get("party_ids_contains"),
                        _err,
                        exc_info=True,
                    )
                    return {"current": [], "historic": []}

            # Per-source current/historic payload buckets (D4). When no term window
            # resolves, everything lands in the *current* buckets via single-pass
            # retrieve() and the historic buckets stay empty — preserving the exact
            # pre-Phase-09 grounding for federal-default and general contexts (SC4).
            manifesto_current: list[dict] = []
            speech_current: list[dict] = []
            vote_current: list[dict] = []
            manifesto_historic: list[dict] = []
            speech_historic: list[dict] = []
            vote_historic: list[dict] = []

            if party.party_id != WAHL_CHAT_PARTY.party_id:
                # Vote records: filtered via party_ids_contains (vote_record chunks
                # have a party_ids ARRAY, no single tenant party_id).
                # Manifesto records: filtered by party_id (tenant owner).
                # Parliamentary speeches: filtered by party_id (tenant owner).
                # region_path is the election scope — MatchAny on the chunk-level
                # scalar `region` field.  Federal default = ["DE"].
                if term_window is not None:
                    # TWO-PASS temporal retrieval (Phase 09, D1/D3/D4). A window
                    # resolved, so each source is split into a current pass
                    # (publish_date ∈ [term_start, term_end], EXISTING per-source
                    # current limits) and a small high-bar historic pass
                    # (publish_date < term_start). ONE query vector is reused across
                    # all six passes (query_vector=rag_query_vector). legislature_period_id
                    # + level are forwarded to the vote two-pass ONLY (vote-only rule);
                    # retrieve_two_pass forwards level to both passes and
                    # legislature_period_id to the current pass only.
                    term_start, term_end = term_window
                    _vote_coro = _safe_two_pass(
                        query_vector=rag_query_vector,
                        source_type="vote_record",
                        party_ids_contains=party.party_id,
                        term_start=term_start,
                        term_end=term_end,
                        current_limit=_CURRENT_VOTE_LIMIT,
                        historic_limit=_HISTORIC_LIMITS["vote"],
                        current_score_threshold=_CHAT_SCORE_THRESHOLD,
                        historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                        region_path=region_path,
                        legislature_period_id=legislature_period_id,
                        level=election_level,   # NOT passed to manifesto/speech
                    )
                    # legislature_period_id and level scope ONLY vote_record — never
                    # passed to manifesto/speech (those chunks lack the fields, so the
                    # MatchValue filter would match nothing and strip their grounding).
                    _manifesto_coro = _safe_two_pass(
                        query_vector=rag_query_vector,
                        source_type="party_manifesto",
                        party_id=party.party_id,
                        term_start=term_start,
                        term_end=term_end,
                        current_limit=_CURRENT_MANIFESTO_LIMIT,
                        historic_limit=_HISTORIC_LIMITS["manifesto"],
                        current_score_threshold=_CHAT_SCORE_THRESHOLD,
                        historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                        region_path=region_path,
                    )
                    # Speeches are fetched at the adaptive FALLBACK ceiling and
                    # trimmed to _CURRENT_SPEECH_LIMIT after the gather ONLY when
                    # official data (votes+manifesto) is present (D4).
                    _speech_coro = _safe_two_pass(
                        query_vector=rag_query_vector,
                        source_type="parliamentary_speech",
                        party_id=party.party_id,
                        term_start=term_start,
                        term_end=term_end,
                        current_limit=_CURRENT_SPEECH_FALLBACK,
                        historic_limit=_HISTORIC_LIMITS["speech"],
                        current_score_threshold=_CHAT_SCORE_THRESHOLD,
                        historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                        region_path=region_path,
                    )
                    vote_buckets, manifesto_buckets, speech_buckets = (
                        await asyncio.gather(_vote_coro, _manifesto_coro, _speech_coro)
                    )
                    vote_current, vote_historic = (
                        vote_buckets["current"], vote_buckets["historic"]
                    )
                    manifesto_current, manifesto_historic = (
                        manifesto_buckets["current"], manifesto_buckets["historic"]
                    )
                    speech_current, speech_historic = (
                        speech_buckets["current"], speech_buckets["historic"]
                    )
                else:
                    # SINGLE-PASS fallback — no window resolved. Byte-for-byte the
                    # pre-Phase-09 grounding; historic buckets stay empty. Distinct
                    # variable names from the two-pass branch above: these coroutines
                    # return list[dict], the two-pass ones dict[str, list[dict]], and
                    # reusing one name would make the types collide for the checker.
                    _vote_coro_sp = _safe_retrieve(
                        improved_rag_query,
                        query_vector=rag_query_vector,
                        source_type="vote_record",
                        party_ids_contains=party.party_id,
                        limit=_CURRENT_VOTE_LIMIT,
                        score_threshold=_CHAT_SCORE_THRESHOLD,
                        region_path=region_path,
                        legislature_period_id=legislature_period_id,
                        level=election_level,   # NOT passed to manifesto/speech
                    )
                    _manifesto_coro_sp = _safe_retrieve(
                        improved_rag_query,
                        query_vector=rag_query_vector,
                        source_type="party_manifesto",
                        party_id=party.party_id,
                        limit=_CURRENT_MANIFESTO_LIMIT,
                        score_threshold=_CHAT_SCORE_THRESHOLD,
                        region_path=region_path,
                    )
                    # Fetch speeches at the adaptive FALLBACK ceiling; trimmed to
                    # _CURRENT_SPEECH_LIMIT after the gather when official data is present.
                    _speech_coro_sp = _safe_retrieve(
                        improved_rag_query,
                        query_vector=rag_query_vector,
                        source_type="parliamentary_speech",
                        party_id=party.party_id,
                        limit=_CURRENT_SPEECH_FALLBACK,
                        score_threshold=_CHAT_SCORE_THRESHOLD,
                        region_path=region_path,
                    )
                    vote_current, manifesto_current, speech_current = (
                        await asyncio.gather(
                            _vote_coro_sp, _manifesto_coro_sp, _speech_coro_sp
                        )
                    )

            # Document builders (_mk_manifesto_docs / _mk_speech_docs) are shared
            # module-level helpers so this single-party path and the comparison
            # path stay byte-for-byte in sync.

            # Build the current-bucket vote Documents ONCE (participation-filtered),
            # then apply the adaptive speech trim (D4): when official data
            # (votes+manifesto) is NOT sparse, drop speeches back to the normal cap;
            # when sparse, keep the fetched-at-ceiling speeches so the answer isn't
            # starved. Historic speeches are never trimmed (kept small per Phase 09).
            vote_docs_current = build_vote_documents(
                party.party_id, party.name, vote_current
            )
            votes_absent, manifesto_absent = _official_coverage(
                vote_docs_current, manifesto_current
            )
            # Phase 10 (D3): the historic bucket is already high-bar threshold-gated
            # at retrieval, so a non-empty raw historic payload means "cleared the
            # bar" — enough to instruct a marked historic section. Drives has_historic
            # threaded into generation below.
            has_historic = bool(
                manifesto_historic or speech_historic or vote_historic
            )
            if not votes_absent and not manifesto_absent:
                speech_current = speech_current[:_CURRENT_SPEECH_LIMIT]

            # combined_docs is the single list passed to generate_streaming_chatbot_response.
            # Order (D1/D4): CURRENT bucket first (manifesto → vote → speech — votes
            # precede speeches so the model leads with position then record, treating
            # speeches as supporting material), then the HISTORIC bucket in the SAME
            # source order. build_vote_documents drops non-participating votes, so vote
            # doc counts equal the participation-filtered sources[] entries below
            # (citation alignment). Per-section rendering is DEFERRED — both buckets
            # feed the SAME combined grounding.
            combined_docs = (
                _mk_manifesto_docs(manifesto_current)
                + vote_docs_current
                + _mk_speech_docs(speech_current, improved_rag_query)
                + _mk_manifesto_docs(manifesto_historic)
                + build_vote_documents(party.party_id, party.name, vote_historic)
                + _mk_speech_docs(speech_historic, improved_rag_query)
            )

            # ---- sources[] builders (mirror combined_docs order EXACTLY) -------
            # sources[] must be appended in the IDENTICAL bucket-then-source order as
            # combined_docs so [N] maps to sources[N]. CURRENT first, HISTORIC after;
            # within each bucket manifesto → vote → speech.
            def _append_manifesto_sources(payloads: list[dict]) -> None:
                for manifesto_payload in payloads:
                    meta = manifesto_payload.get("meta") or {}
                    # Manifestos are always PDF-backed → eligible for a `#search=`
                    # highlight on the cited passage (in addition to the page anchor).
                    manifesto_text = manifesto_payload.get("text")
                    if manifesto_text:
                        highlight_refs.append((len(sources), manifesto_text))
                    sources.append(
                        {
                            "source": manifesto_payload.get("citation_title"),
                            "page": meta.get("page_start"),
                            "document_publish_date": manifesto_payload.get("publish_date"),
                            "url": manifesto_payload.get("citation_url"),
                            "source_document": manifesto_payload.get("citation_title"),
                        }
                    )

            def _append_speech_sources(payloads: list[dict]) -> None:
                for speech_payload in payloads:
                    # op speeches → phrase-level video deep-link + ODbL/Bundestag
                    # attribution (Q8); DIP speeches keep their citation_url and add
                    # no attribution keys.
                    primary_url = _speech_deeplink_url(
                        speech_payload, improved_rag_query
                    )
                    source_entry = {
                        "source": speech_payload.get("citation_title"),
                        "page": 1,
                        "document_publish_date": speech_payload.get("publish_date"),
                        "url": primary_url,
                        "source_document": speech_payload.get("citation_title"),
                    }
                    # Dual-format links (merge, not replace): a speech renders as ONE
                    # source exposing both the op video deep-link and the DIP
                    # transcript PDF. op → primary url is the video + transcript_pdf_url
                    # grafted from the superseded DIP record; dip → primary url is the
                    # PDF. `url` stays the primary (video-first) link for back-compat
                    # and [N] alignment; video_url / pdf_url are additive.
                    meta = speech_payload.get("meta") or {}
                    if speech_payload.get("source") == "op":
                        if _is_video_link(primary_url):
                            source_entry["video_url"] = primary_url
                        transcript_pdf = meta.get("transcript_pdf_url")
                        if transcript_pdf:
                            source_entry["pdf_url"] = transcript_pdf
                    elif speech_payload.get("source") == "dip" and primary_url:
                        source_entry["pdf_url"] = primary_url
                    source_entry.update(_speech_attribution(speech_payload))
                    # Record op speeches with a timed sentence_map so their video
                    # deep-link can be refined post-generation from the cited claim.
                    if speech_payload.get("source") == "op" and meta.get("sentence_map"):
                        speech_refs.append((len(sources), speech_payload))
                    # A speech with a PDF transcript (DIP always; op when a transcript
                    # was grafted) can gain a `#search=` highlight — DIP has no page map,
                    # so the snippet is its only in-document anchor.
                    speech_text = speech_payload.get("text")
                    if speech_text and source_entry.get("pdf_url"):
                        highlight_refs.append((len(sources), speech_text))
                    sources.append(source_entry)

            def _append_vote_sources(payloads: list[dict]) -> None:
                # Vote citation alignment (CRITICAL): replicate the SAME participation
                # filter build_vote_documents uses, so only participating votes get a
                # sources[] entry and sources[N] stays aligned with combined_docs[N].
                for vote_payload in payloads:
                    meta_vp = (vote_payload.get("meta") or {})
                    results_vp = meta_vp.get("vote_results") or []
                    party_result_vp = next(
                        (r for r in results_vp if r.get("party_id") == party.party_id),
                        None,
                    )
                    if party_result_vp is None:
                        continue  # party did not participate — skip (mirrors build_vote_documents)
                    sources.append(
                        {
                            "source": vote_payload.get("citation_title"),
                            "page": 1,
                            "document_publish_date": vote_payload.get("publish_date"),
                            "url": vote_payload.get("citation_url"),
                            "source_document": vote_payload.get("citation_title"),
                            "region": vote_payload.get("region"),   # structural origin marker
                        }
                    )

            # relevant_docs_list is always [] (dead V1 all_parties query removed) —
            # this loop is a no-op but retained for clarity.
            for source_doc in relevant_docs_list:
                page_raw = source_doc.metadata.get("page", 0)
                page_number = int(page_raw if page_raw is not None else 0) + 1
                sources.append(
                    {
                        "source": source_doc.metadata.get("document_name"),
                        "page": page_number,
                        "document_publish_date": source_doc.metadata.get(
                            "document_publish_date"
                        ),
                        "url": source_doc.metadata.get("url"),
                        "source_document": source_doc.metadata.get("source_document"),
                    }
                )

            # CURRENT bucket sources (manifesto → vote → speech). speech_current is
            # the already-trimmed list, so sources[] stays aligned with combined_docs.
            _append_manifesto_sources(manifesto_current)
            _append_vote_sources(vote_current)
            _append_speech_sources(speech_current)
            # HISTORIC bucket sources — same source order, appended AFTER current.
            _append_manifesto_sources(manifesto_historic)
            _append_vote_sources(vote_historic)
            _append_speech_sources(speech_historic)

            sources_dto = SourcesDto(
                session_id=group_chat_session.session_id,
                party_id=party.party_id,
                rag_query=improved_rag_query_list,
                sources=sources,
            )
            # 8: sources_ready (replaces V1 socket_emit("sources_ready", ...))
            yield _frame("8", {"type": "sources_ready", **sources_dto.model_dump()})

        else:
            relevant_docs_dict = dict(relevant_docs) if relevant_docs else {}  # type: ignore[arg-type]
            if parties_being_compared:
                for rel_party in parties_being_compared:
                    for source_doc in relevant_docs_dict.get(rel_party.party_id, []):
                        page_raw = source_doc.metadata.get("page", 0)
                        page_number = int(page_raw if page_raw is not None else 0) + 1
                        sources.append(
                            {
                                "source": source_doc.metadata.get("document_name"),
                                "page": page_number,
                                "document_publish_date": source_doc.metadata.get(
                                    "document_publish_date"
                                ),
                                "url": source_doc.metadata.get("url"),
                                "source_document": source_doc.metadata.get(
                                    "source_document"
                                ),
                                "party_id": rel_party.party_id,
                            }
                        )

            sources_dto = SourcesDto(
                session_id=group_chat_session.session_id,
                party_id=party.party_id,
                rag_query=improved_rag_query_list,
                sources=sources,
            )
            yield _frame("8", {"type": "sources_ready", **sources_dto.model_dump()})

        # LLM streaming
        if not is_comparing_question:
            # Phase 10 (D1–D5): thread the sparse-official-data coverage signal
            # (_official_coverage, computed above from the participation-filtered
            # vote docs + manifesto payloads) and has_historic into generation so
            # the answer follows the four-section shape, marks historic material,
            # and is transparent when official data is thin.
            chunk_stream = await generate_streaming_chatbot_response(
                party,
                conversation_history_str,
                question_for_party,
                combined_docs,
                all_parties=all_available_parties,
                chat_response_llm_size=group_chat_session.chat_response_llm_size,
                context_id=group_chat_session.context_id,
                use_premium_llms=use_premium_llms,
                election_level=election_level,
                # Positive coverage preamble: name the source types that DO ground
                # the answer (manifesto / votes / speeches present), replacing the
                # old absent-source flagging. Presence mirrors the buckets that feed
                # combined_docs above; speech_current is the already-trimmed list.
                present_sources=(
                    not manifesto_absent,
                    not votes_absent,
                    len(speech_current) > 0,
                ),
                has_historic=has_historic,
            )
        else:
            # Comparison keeps its own by-party structure; only the D3 historic
            # marking is threaded (coverage transparency is single-party only).
            # has_historic is re-derived from the merged comparison grounding
            # (publish_date < term_start) since process_party leaves no per-doc marker.
            chunk_stream = await generate_streaming_chatbot_comparing_response(
                party,
                conversation_history_str,
                question_for_party,
                relevant_docs_dict or {},
                parties_being_compared or [],
                chat_response_llm_size=group_chat_session.chat_response_llm_size,
                use_premium_llms=use_premium_llms,
                election_level=election_level,
                has_historic=_has_historic_docs(relevant_docs_dict, term_window),
            )

        # v5 text block — one id for the whole party answer's deltas.
        message_id = str(uuid.uuid4())
        yield _text_start(message_id)
        async for message_chunk in chunk_stream:
            chunk_content = message_chunk.content
            if (
                isinstance(chunk_content, dict)
                and chunk_content.get("type", "text") != "text"
            ):
                continue

            if full_response is None:
                full_response = message_chunk
            else:
                full_response += message_chunk

            chunk_text = message_chunk.text
            for i in range(0, len(chunk_text), MAX_RESPONSE_CHUNK_LENGTH):
                if i > 0:
                    await asyncio.sleep(0.025)
                split_chunk = chunk_text[i : i + MAX_RESPONSE_CHUNK_LENGTH]
                yield _text_delta(message_id, split_chunk)
                yield _party_chunk(
                    group_chat_session.session_id, party.party_id, split_chunk
                )
        yield _text_end(message_id)

        # Finalise
        full_response_text = full_response.text if full_response else ""
        full_response_text = sanitize_references(full_response_text)

        # Post-generation source refinement (now the answer exists): (1) re-point
        # each cited op speech's video deep-link at the sentence the model actually
        # asserted, not the pre-answer RAG-query guess (D-02b); (2) attach a
        # best-effort `#search=` highlight snippet to each cited PDF source from that
        # same claim. Either mutation → re-emit sources_ready (the client overwrites
        # the prior sources for this party).
        deeplinks_changed = _refine_speech_deeplinks(
            sources, speech_refs, full_response_text
        )
        highlights_changed = _refine_pdf_highlights(
            sources, highlight_refs, full_response_text
        )
        if deeplinks_changed or highlights_changed:
            refined_dto = SourcesDto(
                session_id=group_chat_session.session_id,
                party_id=party.party_id,
                rag_query=improved_rag_query_list,
                sources=sources,
            )
            yield _frame("8", {"type": "sources_ready", **refined_dto.model_dump()})

        chatbot_message = Message(
            id=message_id,
            role="assistant",
            content=full_response_text,
            sources=sources,
            party_id=party.party_id,
            current_chat_title=group_chat_session.title,
            quick_replies=[],
            rag_query=improved_rag_query_list,
        )
        group_chat_session.chat_history.append(chatbot_message)

        party_response_complete_dto = PartyResponseCompleteDto(
            session_id=group_chat_session.session_id,
            party_id=party.party_id,
            complete_message=full_response_text,
            message_id=message_id,
            status=Status(indicator=StatusIndicator.SUCCESS, message="Success"),
        )
        # 8: party_complete (replaces V1 socket_emit("party_response_complete", ...))
        yield _frame(
            "8",
            {"type": "party_complete", **party_response_complete_dto.model_dump()},
        )
        logger.info(
            f"Party response for {party.party_id} yielded (message_id={message_id})"
        )

        # Cache newly-generated response.
        # Cancellation safety: this code is only reached after the full
        # LLM stream has been consumed (the async for loop above must complete).
        # If the outer loop in generate_chat_stream breaks due to client disconnect
        # or budget expiry, this generator is abandoned and this code never runs —
        # so partial responses are never written to the cache.
        if cache_key is not None and cached_answer_to_emit is None:
            cached_answer = CachedResponse(
                content=full_response_text,
                sources=sources,
                rag_query=improved_rag_query_list,
                created_at=datetime.now(),
                cached_conversation_history=cache_conversation_history_str,
                depth=len(group_chat_session.chat_history),
                user_message_depth=len(
                    [m for m in group_chat_session.chat_history if m.role == Role.USER]
                ),
            )
            await awrite_cached_answer_for_party(party.party_id, cache_key, cached_answer)

    except openai.BadRequestError as e:
        logger.error(
            f"BadRequestError for party {party.party_id}: {e}", exc_info=True
        )
        yield _frame(
            "8",
            {
                "type": "party_complete",
                "session_id": group_chat_session.session_id,
                "party_id": party.party_id,
                "complete_message": "Diese Frage kann ich leider nicht beantworten.",
                "message_id": None,
                "status": {"indicator": "error", "message": str(e)},
            },
        )
    except Exception as e:
        logger.error(
            f"Error fetching party response for {party.party_id}: {e}", exc_info=True
        )
        yield _frame(
            "8",
            {
                "type": "party_complete",
                "session_id": group_chat_session.session_id,
                "party_id": party.party_id,
                "complete_message": "Es tut mir Leid, leider ist ein Fehler aufgetreten. Bitte versuche es später erneut.",
                "message_id": None,
                "status": {"indicator": "error", "message": str(e)},
            },
        )


# ---------------------------------------------------------------------------
# Comparison-question doc fetcher — grounded from single store
# ---------------------------------------------------------------------------
async def process_party(
    party: ContextParty,
    chat_history_str: str,
    general_question: str,
    relevant_doc_dict: Dict[str, List[Document]],
    lock: asyncio.Lock,
    improved_rag_query_list: List[str],
    context_id: str,
    region_path: Optional[List[str]] = None,
    legislature_period_id: Optional[int] = None,
    election_level: Optional[str] = None,
    term_window: Optional[tuple[datetime, datetime]] = None,
) -> None:
    """Fetch relevant docs for one party in a comparison question (no emit).

    Previously called identify_relevant_docs_with_llm_based_reranking which
    queried the EMPTY all_parties_dev / context collection — answers were completely
    ungrounded. Now embeds the rag query ONCE and retrieves manifesto + speech + vote
    documents from the single wahlchat_chunks store, mirroring the single-party path.
    """
    improved_rag_query = await generate_improvement_rag_query(
        party, chat_history_str, general_question, context_id=context_id
    )
    # Embed once, reuse for all three sources (same pattern as single-party path).
    rag_query_vector = await embed.aembed_query(improved_rag_query)

    async def _safe_retrieve_cmp(*args, **kwargs) -> list[dict]:  # type: ignore[no-untyped-def]
        """Wrap retrieve() so a failure returns [] rather than raising."""
        try:
            # with_scores=False here → list[dict]; narrow retrieve()'s union return.
            return cast(
                list[dict], await asyncio.to_thread(retrieve, *args, **kwargs)
            )
        except Exception as _err:  # noqa: BLE001
            logger.warning(
                "comparison retrieve() failed (source=%s party=%s): %s",
                kwargs.get("source_type"),
                kwargs.get("party_id") or kwargs.get("party_ids_contains"),
                _err,
                exc_info=True,
            )
            return []

    async def _safe_two_pass_cmp(**kwargs) -> dict[str, list[dict]]:  # type: ignore[no-untyped-def]
        """Wrap retrieve_two_pass() so a failure returns empty buckets."""
        try:
            return await asyncio.to_thread(
                retrieve_two_pass, improved_rag_query, **kwargs
            )
        except Exception as _err:  # noqa: BLE001
            logger.warning(
                "comparison retrieve_two_pass() failed (source=%s party=%s): %s",
                kwargs.get("source_type"),
                kwargs.get("party_id") or kwargs.get("party_ids_contains"),
                _err,
                exc_info=True,
            )
            return {"current": [], "historic": []}

    # Per-source current/historic buckets (mirrors the single-party path).
    manifesto_current: list[dict] = []
    speech_current: list[dict] = []
    vote_current: list[dict] = []
    manifesto_historic: list[dict] = []
    speech_historic: list[dict] = []
    vote_historic: list[dict] = []

    if party.party_id != WAHL_CHAT_PARTY.party_id:
        # Run all three source retrievals concurrently for this party.
        if term_window is not None:
            # TWO-PASS temporal retrieval (D1/D3/D4) — same wiring as the
            # single-party path: current window [term_start, term_end] with the
            # existing per-source limits, plus a small high-bar historic bucket.
            # One query vector reused across all six passes; legislature_period_id
            # + level forwarded to the vote two-pass ONLY.
            term_start, term_end = term_window
            _vote_coro = _safe_two_pass_cmp(
                query_vector=rag_query_vector,
                source_type="vote_record",
                party_ids_contains=party.party_id,
                term_start=term_start,
                term_end=term_end,
                current_limit=_CURRENT_VOTE_LIMIT,
                historic_limit=_HISTORIC_LIMITS["vote"],
                current_score_threshold=_CHAT_SCORE_THRESHOLD,
                historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                region_path=region_path,
                legislature_period_id=legislature_period_id,
                level=election_level,   # vote-only
            )
            # legislature_period_id and level scope ONLY vote_record (see single-party path).
            _manifesto_coro = _safe_two_pass_cmp(
                query_vector=rag_query_vector,
                source_type="party_manifesto",
                party_id=party.party_id,
                term_start=term_start,
                term_end=term_end,
                current_limit=_CURRENT_MANIFESTO_LIMIT,
                historic_limit=_HISTORIC_LIMITS["manifesto"],
                current_score_threshold=_CHAT_SCORE_THRESHOLD,
                historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                region_path=region_path,
            )
            # Speeches fetched at the adaptive FALLBACK ceiling; trimmed below when
            # official data is present (mirrors the single-party path).
            _speech_coro = _safe_two_pass_cmp(
                query_vector=rag_query_vector,
                source_type="parliamentary_speech",
                party_id=party.party_id,
                term_start=term_start,
                term_end=term_end,
                current_limit=_CURRENT_SPEECH_FALLBACK,
                historic_limit=_HISTORIC_LIMITS["speech"],
                current_score_threshold=_CHAT_SCORE_THRESHOLD,
                historic_score_threshold=_HISTORIC_SCORE_THRESHOLD,
                region_path=region_path,
            )
            vote_buckets, manifesto_buckets, speech_buckets = await asyncio.gather(
                _vote_coro, _manifesto_coro, _speech_coro
            )
            vote_current, vote_historic = (
                vote_buckets["current"], vote_buckets["historic"]
            )
            manifesto_current, manifesto_historic = (
                manifesto_buckets["current"], manifesto_buckets["historic"]
            )
            speech_current, speech_historic = (
                speech_buckets["current"], speech_buckets["historic"]
            )
        else:
            # SINGLE-PASS fallback — no window resolved. Unchanged pre-Phase-09
            # comparison grounding; historic buckets stay empty. Distinct variable
            # names from the two-pass branch above: these coroutines return list[dict],
            # the two-pass ones dict[str, list[dict]], so a shared name would collide.
            _vote_coro_sp = _safe_retrieve_cmp(
                improved_rag_query,
                query_vector=rag_query_vector,
                source_type="vote_record",
                party_ids_contains=party.party_id,
                limit=_CURRENT_VOTE_LIMIT,
                score_threshold=_CHAT_SCORE_THRESHOLD,
                region_path=region_path,
                legislature_period_id=legislature_period_id,
                level=election_level,   # vote-only
            )
            _manifesto_coro_sp = _safe_retrieve_cmp(
                improved_rag_query,
                query_vector=rag_query_vector,
                source_type="party_manifesto",
                party_id=party.party_id,
                limit=_CURRENT_MANIFESTO_LIMIT,
                score_threshold=_CHAT_SCORE_THRESHOLD,
                region_path=region_path,
            )
            # Fetch speeches at the adaptive FALLBACK ceiling; trimmed below when present.
            _speech_coro_sp = _safe_retrieve_cmp(
                improved_rag_query,
                query_vector=rag_query_vector,
                source_type="parliamentary_speech",
                party_id=party.party_id,
                limit=_CURRENT_SPEECH_FALLBACK,
                score_threshold=_CHAT_SCORE_THRESHOLD,
                region_path=region_path,
            )
            vote_current, manifesto_current, speech_current = await asyncio.gather(
                _vote_coro_sp, _manifesto_coro_sp, _speech_coro_sp
            )

    # Documents are built via the shared module-level _mk_manifesto_docs /
    # _mk_speech_docs helpers (identical to the single-party path).

    # Build the current-bucket vote Documents ONCE (participation-filtered), then
    # apply the adaptive speech trim (D4): drop speeches to the normal cap when
    # official data (votes+manifesto) is present; keep the fetched-at-ceiling
    # speeches when official data is sparse. Mirrors the single-party path.
    vote_docs_current = build_vote_documents(party.party_id, party.name, vote_current)
    votes_absent, manifesto_absent = _official_coverage(
        vote_docs_current, manifesto_current
    )
    if not votes_absent and not manifesto_absent:
        speech_current = speech_current[:_CURRENT_SPEECH_LIMIT]

    # Merge current-first, historic-after (D1/D4) in manifesto → vote → speech order
    # so [N] citations built downstream (from document_name metadata) stay aligned
    # with the same bucket-then-source order used by the single-party path.
    grounded_docs = (
        _mk_manifesto_docs(manifesto_current)
        + vote_docs_current
        + _mk_speech_docs(speech_current, improved_rag_query)
        + _mk_manifesto_docs(manifesto_historic)
        + build_vote_documents(party.party_id, party.name, vote_historic)
        + _mk_speech_docs(speech_historic, improved_rag_query)
    )

    async with lock:
        improved_rag_query_list.append(improved_rag_query)
    async with lock:
        relevant_doc_dict[party.party_id] = grounded_docs


# ---------------------------------------------------------------------------
# GDPR cache gate helpers (stateless — evaluated from the request's
# chat_history): only curated conversations may be cached. Political opinions
# are special-category data (GDPR Art. 9); free-text conversations must never
# be written to the cross-user party answer cache.
# ---------------------------------------------------------------------------
def _conversation_is_quick_reply_driven(chat_history: List[Message]) -> bool:
    """True iff every user turn AFTER the first was selected from the
    immediately-preceding assistant message's quick_replies.

    The web client attaches the group-level quick_replies to every assistant
    message in chat_history, so each assistant message carries the replies it
    offered for the following user turn. Any missing preceding assistant
    message, missing/empty quick_replies, or a user turn whose content was not
    offered → False (default NOT cacheable when signals are missing).

    A single-user-turn history returns True — first-turn curation is handled
    by the proposed-question check at the gate site.
    """
    first_user_seen = False
    for idx, msg in enumerate(chat_history):
        if msg.role != Role.USER:
            continue
        if not first_user_seen:
            first_user_seen = True
            continue
        preceding = chat_history[idx - 1] if idx > 0 else None
        if preceding is None or preceding.role != Role.ASSISTANT:
            return False
        if not preceding.quick_replies:
            return False
        if msg.content not in preceding.quick_replies:
            return False
    return True


def _is_curated_conversation(
    chat_history: List[Message],
    proposed_questions: List[str],
    proposed_questions_group: List[str],
) -> bool:
    """True iff the conversation is fully curated: the first user message is a
    proposed question AND every follow-up user turn is quick-reply-driven.

    Only curated conversations are safe to cache — their content is authored
    by wahl.chat, not the user, so no special-category data (GDPR Art. 9) can
    leak cross-user via the party answer cache.
    """
    first_user_msg = next(
        (msg for msg in chat_history if msg.role == Role.USER), None
    )
    if first_user_msg is None:
        return False
    first_curated = (
        first_user_msg.content in proposed_questions
        or first_user_msg.content in proposed_questions_group
    )
    return first_curated and _conversation_is_quick_reply_driven(chat_history)


# ---------------------------------------------------------------------------
# Main SSE generator — replaces generate_chat_answer
# ---------------------------------------------------------------------------
async def generate_chat_stream(  # type: ignore[no-untyped-def]
    body,
    request: Optional[FastAPIRequest] = None,
) -> AsyncGenerator[str, None]:
    """Stateless SSE generator for POST /api/v1/chat.

    Takes a ChatRequestDto (body) from the route handler; the client sends the
    full chat_history per request (stateless design).

    Emits Vercel AI SDK data-stream protocol:
      f  — frame init
      8  — data annotation (responding_parties, sources_ready, party_complete, quick_replies_title)
      0  — text delta
      e  — step finish
      d  — final summary
      [DONE] — stream end

    Multi-party: SERIALIZED — parties respond one at a time.
    Concurrent streaming could later multiplex via asyncio.Queue if required.

    Args:
        body:    ChatRequestDto from the route handler.
        request: Optional FastAPI Request for disconnect detection.
                 When supplied, generation stops between parties or between
                 deltas when the client has disconnected.
    """
    # Record wall-clock start time for per-stream budget enforcement.
    _stream_start = time.monotonic()

    message_id = str(uuid.uuid4())

    # f: frame init
    yield _frame("f", {"messageId": message_id})

    # Reconstruct stateless GroupChatSession from request body
    user_message = Message(
        id=message_id,
        role="user",
        content=body.user_message,
    )

    # Build chat history from request body (stateless model)
    from src.models.chat import GroupChatSession as _GroupChatSession  # local import avoids circular
    from src.models.general import LLMSize

    chat_history: list[Message] = []
    for raw_msg in body.chat_history:
        if isinstance(raw_msg, Message):
            chat_history.append(raw_msg)
        elif isinstance(raw_msg, dict):
            try:
                chat_history.append(Message(**raw_msg))
            except Exception:
                pass  # skip malformed history entries

    # Append current user message if not a duplicate
    if not chat_history or chat_history[-1].content != user_message.content:
        chat_history.append(user_message)

    group_chat_session = _GroupChatSession(
        session_id=body.session_id,
        context_id=body.context_id,
        chat_history=chat_history,
        chat_response_llm_size=LLMSize.LARGE,
    )

    # cacheable only for quick-reply-driven sessions
    is_beginning_of_chat = len(chat_history) == 1

    try:
        all_parties = await aget_parties_for_context(body.context_id)
        # Fetch context ONCE; derive region_path and legislature_period_id for
        # election-scoped retrieval. All retrieve() calls in both paths reuse these.
        _context = await aget_context_by_id(body.context_id)
        region_path: List[str] = _context.region_path if _context is not None else ["DE"]
        # AW parliament_period ID for period-scoped vote retrieval.
        # Passed ONLY to vote_record retrieve() calls. Manifesto/speech
        # chunks do not carry this field, so applying it as a MatchValue filter
        # would match nothing and strip their grounding whenever a context sets it.
        legislature_period_id: Optional[int] = (
            _context.legislature_period_id if _context is not None else None
        )
        # Governance level for the election context.
        # level is passed ONLY to vote_record retrieve() (via election_level).
        # Default None is treated as 'federal' by retrieve() post-fetch re-rank.
        election_level: Optional[str] = (
            _context.level if _context is not None else None
        )
        # Derive the current-term window ONCE from the RAW context values (D5),
        # BEFORE the federal-only nulling of legislature_period_id below — the raw
        # period id lets term_window_for_context resolve the exact legislature row
        # for federal/period-named contexts, while region_path + date resolve state
        # contexts. The resulting [term_start, term_end] drives the two-pass current
        # window for ALL three sources; when None resolves (unknown region / general
        # context), both paths fall back to the existing single-pass retrieve().
        # NOTE: this uses _context.legislature_period_id (the raw value), NOT the
        # federal-only-scoped local variable that gets nulled just below.
        term_window: Optional[tuple[datetime, datetime]] = term_window_for_context(
            region_path,
            _context.legislature_period_id if _context is not None else None,
            _context.date if _context is not None else None,
        )
        # legislature_period_id is a single-value Qdrant filter, so applying it in a
        # non-federal context hard-excludes federal votes (which carry a different period
        # id) and silently disables the federal-vote down-rank. Scope it to FEDERAL
        # contexts only; state/municipal contexts rely on region_path + the post-fetch
        # down-rank to keep federal votes visible but ranked below local votes.
        if election_level not in (None, "federal"):
            legislature_period_id = None
        # A sub-federal region_path with no explicit level falls through as 'federal'
        # (no down-rank, no disclosure). Surface it loudly rather than silently mis-scope.
        if election_level is None and region_path != ["DE"]:
            logger.warning(
                "Context %s has region_path=%s but no 'level' set — federal-vote "
                "down-rank and disclosure are skipped (treated as federal). Set "
                "Context.level to 'state'/'municipal' for sub-federal elections.",
                body.context_id,
                region_path,
            )

        pre_selected_parties = [
            p for p in all_parties if p.party_id in body.party_ids
        ]
        pre_selected_party_ids = [p.party_id for p in pre_selected_parties]

        chat_history_without_last = chat_history[:-1]
        chat_history_str = build_chat_history_string(
            chat_history_without_last, all_parties
        )

        try:
            (
                party_id_list,
                general_question,
                is_comparing_question,
            ) = await get_question_targets_and_type(
                user_message=user_message.content,
                previous_chat_history=chat_history_str,
                all_available_parties=all_parties + [WAHL_CHAT_PARTY],
                currently_selected_parties=pre_selected_parties,
            )
        except openai.BadRequestError as e:
            logger.error(f"Error identifying question targets: {e}", exc_info=True)
            # Fallback to wahl-chat
            party_id_list = [WAHL_CHAT_PARTY.party_id]
            general_question = user_message.content
            is_comparing_question = False
            yield _frame(
                "8",
                {
                    "type": "responding_parties",
                    "session_id": body.session_id,
                    "party_ids": party_id_list,
                },
            )
            yield _frame(
                "8",
                {
                    "type": "party_complete",
                    "session_id": body.session_id,
                    "party_id": WAHL_CHAT_PARTY.party_id,
                    "complete_message": "Diese Frage kann ich leider nicht beantworten.",
                    "message_id": None,
                    "status": {"indicator": "error", "message": str(e)},
                },
            )
            yield _frame("e", {"finishReason": "stop", "usage": {}})
            yield _frame("d", {"finishReason": "stop", "usage": {}})
            yield "data: [DONE]\n\n"
            return

        if not party_id_list:
            party_id_list = ["wahl-chat"]
        elif is_beginning_of_chat and len(party_id_list) > 7:
            party_id_list = ["wahl-chat"]

        parties_to_respond = [
            p
            for p in all_parties + [WAHL_CHAT_PARTY]
            if p.party_id in party_id_list
        ]

        responding_party_ids = (
            party_id_list if not is_comparing_question else ["wahl-chat"]
        )

        # 8: responding_parties (replaces V1 socket_emit("responding_parties_selected", ...))
        yield _frame(
            "8",
            {
                "type": "responding_parties",
                "session_id": body.session_id,
                "party_ids": responding_party_ids,
            },
        )

        # Collect party generators to iterate SEQUENTIALLY.
        # NOTE: parties respond one at a time.
        # A future asyncio.Queue could multiplex concurrent streams.
        if len(parties_to_respond) == 1 or not is_comparing_question:
            party_generators = []
            for party in parties_to_respond:
                proposed_questions = await aget_proposed_questions_for_party(
                    party.party_id
                )
                proposed_questions_group = await aget_proposed_questions_for_party(
                    "group"
                )
                is_proposed_question = (
                    user_message.content in proposed_questions
                    or user_message.content in proposed_questions_group
                )
                # GDPR cache gate: only curated conversations (proposed-question
                # first turn + every follow-up chosen from the preceding
                # assistant message's quick_replies) may be cached by
                # chat-history hash. Free-text turns carry user-authored
                # political opinions (GDPR Art. 9 special-category data) and
                # must never be replayable cross-user. On a first-turn request
                # this is equivalent to the old `is_beginning_of_chat and not
                # is_proposed_question` gate; it additionally blocks
                # non-curated follow-ups. Default: NOT cacheable.
                if not _is_curated_conversation(
                    chat_history, proposed_questions, proposed_questions_group
                ):
                    group_chat_session.is_cacheable = False
                party_generators.append(
                    fetch_party_response_stream(
                        party,
                        chat_history_str,
                        general_question,
                        group_chat_session,
                        all_available_parties=all_parties,
                        use_premium_llms=body.user_is_logged_in,
                        is_proposed_question=is_proposed_question,
                        is_cacheable_chat=group_chat_session.is_cacheable,
                        region_path=region_path,
                        legislature_period_id=legislature_period_id,
                        election_level=election_level,
                        term_window=term_window,
                    )
                )
        else:
            group_chat_session.is_cacheable = False
            parties_being_compared = parties_to_respond
            relevant_doc_dict: dict[str, list] = {}
            improved_rag_query_list: list[str] = []
            lock = asyncio.Lock()
            party_tasks = [
                process_party(
                    p,
                    chat_history_str,
                    general_question,
                    relevant_doc_dict,
                    lock,
                    improved_rag_query_list,
                    context_id=body.context_id,
                    region_path=region_path,
                    legislature_period_id=legislature_period_id,
                    election_level=election_level,
                    term_window=term_window,
                )
                for p in parties_being_compared
            ]
            try:
                # Parallel RAG doc fetch for comparison questions (NOT streaming output).
                # The SSE stream output is SERIALIZED below.
                await asyncio.wait_for(asyncio.gather(*party_tasks), timeout=40)
            except asyncio.TimeoutError as e:
                logger.error(f"Timeout fetching comparison docs: {e}")
                yield _frame("e", {"finishReason": "stop", "usage": {}})
                yield _frame("d", {"finishReason": "stop", "usage": {}})
                yield "data: [DONE]\n\n"
                return

            party_generators = [
                fetch_party_response_stream(
                    WAHL_CHAT_PARTY,
                    chat_history_str,
                    user_message.content,
                    group_chat_session,
                    all_available_parties=all_parties,
                    use_premium_llms=body.user_is_logged_in,
                    is_cacheable_chat=group_chat_session.is_cacheable,
                    relevant_docs=relevant_doc_dict,
                    parties_being_compared=parties_being_compared,
                    is_comparing_question=is_comparing_question,
                    improved_rag_query_list=improved_rag_query_list,
                    region_path=region_path,
                    legislature_period_id=legislature_period_id,
                    election_level=election_level,
                    term_window=term_window,
                )
            ]

        # SERIALIZED multi-party iteration (see module docstring)
        # Check client disconnect and wall-clock budget between parties.
        for gen in party_generators:
            # bail out between parties when client has disconnected.
            if request is not None and await request.is_disconnected():
                logger.info("generate_chat_stream: client disconnected — stopping generation")
                break

            # enforce per-stream wall-clock budget between parties.
            if time.monotonic() - _stream_start > _CHAT_STREAM_BUDGET_S:
                logger.warning(
                    "generate_chat_stream: per-stream budget of %ds exceeded — stopping",
                    _CHAT_STREAM_BUDGET_S,
                )
                break

            try:
                async for event in gen:
                    yield event
            except asyncio.TimeoutError:
                # Previously dead code (nothing inside raised TimeoutError).
                # now reachable if asyncio.timeout is added; kept for safety.
                logger.error("Timeout iterating party generator")
                break

    except Exception as e:
        logger.error(f"Unexpected error in generate_chat_stream: {e}", exc_info=True)
        yield _frame("8", {"type": "error", "message": str(e)})
        yield _frame("e", {"finishReason": "stop", "usage": {}})
        yield _frame("d", {"finishReason": "stop", "usage": {}})
        yield "data: [DONE]\n\n"
        return

    # Quick replies + title (replaces V1 socket_emit("quick_replies_and_title_ready", ...))
    try:
        full_chat_history_str = build_chat_history_string(
            group_chat_session.chat_history, all_parties
        )
        ids_in_chat = set(pre_selected_party_ids + party_id_list)
        parties_in_chat = [p for p in all_parties if p.party_id in ids_in_chat]

        chat_title_and_qr = await generate_chat_title_and_chick_replies(
            chat_history_str=full_chat_history_str,
            chat_title=group_chat_session.title or "Noch kein Titel vergeben",
            parties_in_chat=parties_in_chat,
            wahl_chat_assistant_last_responded=party_id_list
            == [WAHL_CHAT_PARTY.party_id],
            is_comparing=is_comparing_question,
        )

        quick_replies_dto = QuickRepliesAndTitleDto(
            session_id=body.session_id,
            quick_replies=chat_title_and_qr.quick_replies,
            title=chat_title_and_qr.chat_title,
        )
        # 8: quick_replies_title (replaces V1 socket_emit("quick_replies_and_title_ready", ...))
        yield _frame(
            "8",
            {"type": "quick_replies_title", **quick_replies_dto.model_dump()},
        )
    except Exception as e:
        logger.error(f"Error generating quick replies/title: {e}", exc_info=True)

    # Finish events (replaces V1 socket_emit("chat_response_complete", ...))
    yield _frame("e", {"finishReason": "stop", "usage": {}})
    yield _frame("d", {"finishReason": "stop", "usage": {}})
    yield "data: [DONE]\n\n"
