# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
retrieve() capability over the single wahlchat_chunks_{ENV} collection.

Filtered retrieval by source_type, party_id (tenant), region (MatchAny),
authority_tier, and publish_date over the single Qdrant collection.

This module is STANDALONE — it does NOT import chat_service or vector_store_helper.
The V1 retrieval path is untouched. Retrieval is testable without a live Gemini
call (call retrieve() directly with a mocked embed).

Gemini tool declaration:
    Use ``retrieve_schema`` (a Pydantic BaseModel with Literal-typed args) to
    declare the tool surface. Bind via ``llm.bind_tools([retrieve_schema])``.
    Args use ``Literal[...]`` NOT Python Enum — avoids langchain-google-genai
    issue #409 class of bug.

Filter map (full indexed set, setup_collection.py):
    source_type           → FieldCondition(key="source_type",           match=MatchValue)
    party_id              → FieldCondition(key="party_id",              match=MatchValue)  tenant
    region_path           → FieldCondition(key="region",                match=MatchAny)
    authority_tier        → FieldCondition(key="authority_tier",        match=MatchValue)
    publish_after         → FieldCondition(key="publish_date",          match=DatetimeRange(gte=...))
    legislature_period_id → FieldCondition(key="legislature_period_id", match=MatchValue)
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional, Union, cast

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient
from qdrant_client.models import (
    DatetimeRange,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
)

from wahlchat_common.embeddings import get_embeddings
from wahlchat_common.corpus import COLLECTION_NAME, check_fingerprint
from wahlchat_common.governance_levels import ALL_LEVELS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Qdrant client — lazy singleton, mirrors setup_collection.py wiring.
# Deferred to first use so importing this module never opens a network connection.
# ---------------------------------------------------------------------------
_qdrant: Optional[QdrantClient] = None
_embed: Optional[Embeddings] = None

# Clients whose collection fingerprint has been verified this process —
# the check is one extra round-trip, so it runs once per client, not per query.
_fingerprint_checked_clients: set[int] = set()


def _get_qdrant() -> QdrantClient:
    """Return the module-level Qdrant client, initializing on first call."""
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(
            url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
    return _qdrant


def _get_embed() -> Embeddings:
    """Return the module-level embedding model, initializing on first call.

    Deferred initialization avoids raising a provider error at import time when
    the provider's API key is not set (e.g. in CI or test environments that
    override the embed callable via _embed_fn). The concrete provider is resolved
    by get_embeddings() from EMBEDDING_PROVIDER (default OpenAI — unchanged).
    """
    global _embed
    if _embed is None:
        # Search query → RETRIEVAL_QUERY (the query side of Gemini's asymmetric
        # doc/query space; must pair with RETRIEVAL_DOCUMENT at ingest). No-op for
        # OpenAI.
        _embed = get_embeddings(task_type="RETRIEVAL_QUERY")
    return _embed


def _embed_query(query: str, embed_fn: Any = None) -> list[float]:
    """Embed a query string into a dense vector using the locked embedding model.

    Branches on the ``embed_query`` interface FIRST (covers OpenAIEmbeddings and any
    LangChain embeddings — these are NOT callable), then falls back to treating
    ``embed_fn`` as a plain callable (a bare function mock in tests). A
    ``callable()``-first gate would make OpenAIEmbeddings (non-callable) skip the
    embed_query path entirely, which is contradictory.

    Shared by retrieve() and retrieve_two_pass() so the two-pass path embeds ONCE
    and reuses the resulting vector across both passes.
    """
    resolved = embed_fn if embed_fn is not None else _get_embed()
    if hasattr(resolved, "embed_query"):
        return resolved.embed_query(query)
    elif callable(resolved):
        return resolved(query)
    else:
        raise TypeError(
            "retrieve(): embed_fn must expose .embed_query() or be callable; "
            f"got {type(resolved)!r}"
        )


# ---------------------------------------------------------------------------
# Source-type and authority-tier values as Literal types (issue #409).
# Using Literal strings ensures clean JSON-schema generation for Gemini tools;
# Python Enum serialization in langchain-google-genai has historically produced
# unexpected tool-schema shapes (issue #409, PR #453 fixed it but Literal is
# the more explicit and portable choice).
# ---------------------------------------------------------------------------
SourceTypeLiteral = Literal[
    "party_manifesto",
    "vote_record",
    "drucksache",
    "qa_transcript",
    "parliamentary_speech",
]

AuthorityTierLiteral = Literal[
    "authoritative",
    "factual_record",
    "self_reported",
    "promotional",
]

# Chunk provenance within a source_type (op speeches carry video). Indexed keyword.
SourceLiteral = Literal["op", "dip", "upload"]


# ---------------------------------------------------------------------------
# Vote-level re-rank tuning constants.
# Applied only when level is set AND source_type == "vote_record".
# ---------------------------------------------------------------------------
_VOTE_CANDIDATE_MULTIPLIER: int = 10  # over-fetch pool when re-ranking
_VOTE_CANDIDATE_FLOOR: int = 40  # minimum candidate pool so local votes below the
# top-N raw cosine are not starved before the re-rank
_VOTE_DOWNRANK_SMALL: float = (
    0.05  # broader-region vote whose relevance_levels include this level
)
_VOTE_DOWNRANK_LARGE: float = (
    0.20  # broader-region vote whose relevance_levels exclude this level
)


# ---------------------------------------------------------------------------
# Speech prefer-op dedup over-fetch tuning.
# During the transient DIP↔op overlap window a speech can appear as BOTH a
# `dip` and an `op` parliamentary_speech chunk. We over-fetch the speech query
# so the post-fetch dedup collapse (see dedup_prefer_op) does not shrink the
# bucket below its `limit`. Mirrors the vote down-rank over-fetch idiom.
# ---------------------------------------------------------------------------
_SPEECH_CANDIDATE_MULTIPLIER: int = 3
_SPEECH_CANDIDATE_FLOOR: int = 15


def dedup_prefer_op(payloads: list[dict]) -> list[dict]:
    """Collapse a DIP twin into its op counterpart ONLY when the match is unambiguous.

    Post-fetch, pure-Python dedup for ``parliamentary_speech`` payloads. The SAME
    real-world speech can surface as both a ``source=="dip"`` and
    a ``source=="op"`` chunk sharing one ``speech_key``. The op member carries the
    video AND the full speech text, so it is a complete substitute for its DIP
    twin — dropping a *matched* twin loses nothing.

    Why the match must be counted, not assumed 1:1
    ------------------------------------------------
    ``speech_key`` (``de-{ep}-{session}-{speaker}-{agenda}``) is NOT unique per
    speech and there is no exact shared op↔DIP id (op ``speechIndex`` ≠ DIP
    rede-seq; the proceedings text matches only ~99%, not byte-for-byte). Two
    situations put several records under one key:
      * a long speech chunked into several records (shared key + source_item_id);
      * a speaker who speaks twice under the same agenda item — two DISTINCT
        speeches with the same key but DIFFERENT ``source_item_id``.
    Blindly dropping every DIP member whose key an op owns would delete a distinct
    DIP speech that op does NOT have — a grounding/coverage loss.

    Rule (provably lossless, no similarity threshold)
    -------------------------------------------------
    Group by ``speech_key`` and count DISTINCT speeches per source via
    ``source_item_id``:
      * exactly ONE op speech AND exactly ONE dip speech under the key → genuine
        twins → keep the op (all its chunks), graft the dip's transcript PDF, drop
        the dip (all its chunks);
      * any other shape (≥2 distinct op or ≥2 distinct dip, or op-only, or
        dip-only) → keep EVERYTHING. Distinct speeches are never merged; at worst
        the rare true-collision group shows both an op and a dip record (both
        correctly attributed). A missing / None ``speech_key`` is always kept.
    First-seen order is preserved; only matched dip twins are removed.

    This is NEVER a Qdrant ``source`` filter — filtering the query on ``source``
    would break the vote-level down-rank and the two-pass retrieval and violate the
    tenant-only HNSW selective-filter rule. Dedup is post-fetch, exactly like the
    vote-level down-rank.

    Args:
        payloads: Speech payload dicts as returned post-fetch (each may carry
            ``speech_key``, ``source`` and ``source_item_id``).

    Returns:
        The deduped payload list (same dict objects), all op members preserved.
    """
    # Per key: the distinct op / dip speeches (by source_item_id) and the op
    # payload to graft onto. A chunk without a source_item_id counts as its own
    # distinct speech (its id() keeps it from collapsing an unrelated one).
    op_sids: dict[Any, set] = {}
    dip_sids: dict[Any, set] = {}
    op_graft_target: dict[Any, dict] = {}
    for payload in payloads:
        key = payload.get("speech_key")
        if key is None:
            continue
        sid = payload.get("source_item_id", id(payload))
        if payload.get("source") == "op":
            op_sids.setdefault(key, set()).add(sid)
            op_graft_target.setdefault(key, payload)
        elif payload.get("source") == "dip":
            dip_sids.setdefault(key, set()).add(sid)

    def _is_unambiguous_twin(key: Any) -> bool:
        return len(op_sids.get(key, ())) == 1 and len(dip_sids.get(key, ())) == 1

    result: list[dict] = []
    for payload in payloads:
        key = payload.get("speech_key")
        if key is None:
            result.append(payload)  # keyless → never a duplicate
            continue
        if payload.get("source") == "dip" and _is_unambiguous_twin(key):
            # Genuine 1:1 twin of an op speech → graft its PDF and drop it.
            _graft_transcript_pdf(op=op_graft_target[key], dip=payload)
            continue
        result.append(payload)
    return result


def _graft_transcript_pdf(*, op: dict, dip: dict) -> None:
    """Copy a DIP duplicate's transcript PDF onto the surviving op payload.

    Sets ``op["meta"]["transcript_pdf_url"]`` from the dip payload's
    ``citation_url`` (its plenary-protocol PDF) when the op record does not
    already carry one — the query-time mirror of the ingest-time graft in
    ``supersede_dip_duplicates``, so a dual-format speech source works even for
    corpora ingested before the merge landed. Mutates ``op`` in place; no-op when
    the dip has no citation_url.
    """
    pdf_url = dip.get("citation_url")
    if not pdf_url:
        return
    existing_meta = op.get("meta")
    if isinstance(existing_meta, dict) and existing_meta.get("transcript_pdf_url"):
        return  # op already carries a transcript link — keep it.
    # Shallow-copy the meta before setting, so we never mutate a meta dict that may
    # be aliased elsewhere in the retrieval pass; the copy is what op now points at.
    new_meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    new_meta["transcript_pdf_url"] = pdf_url
    op["meta"] = new_meta


# ---------------------------------------------------------------------------
# Historic-bucket recency decay half-life.
# The historic pass can span multiple prior legislature periods; within it we
# apply an exponential recency decay anchored at term_start so more-recent
# history outranks older history at equal cosine similarity. 1826 days ≈ 5 years
# ≈ one legislature period: after one period of age the decay factor halves.
# Tunable.
# ---------------------------------------------------------------------------
_HISTORIC_DECAY_HALFLIFE_DAYS: int = 1826


def _parse_publish_date(value: Any) -> Optional[date]:
    """Parse a payload ``publish_date`` into a ``date``.

    Accepts an ISO ``"YYYY-MM-DD"`` / ``"YYYY-MM-DDTHH:MM:SS"`` string, a
    ``datetime``, or a ``date``. Returns ``None`` when missing or unparseable
    (callers treat ``None`` as "no recency penalty", never a crash).
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# retrieve() — the core retrieval function
# ---------------------------------------------------------------------------


def retrieve(
    query: str,
    source_type: Optional[SourceTypeLiteral] = None,
    party_id: Optional[str] = None,
    party_ids_contains: Optional[str] = None,
    region_path: Optional[list[str]] = None,
    authority_tier: Optional[AuthorityTierLiteral] = None,
    publish_after: Optional[datetime] = None,
    legislature_period_id: Optional[int] = None,
    level: Optional[str] = None,
    limit: int = 5,
    *,
    source: Optional[SourceLiteral] = None,
    publish_range: Optional[DatetimeRange] = None,
    query_vector: Optional[list[float]] = None,
    score_threshold: Optional[float] = None,
    with_scores: bool = False,
    _client: Optional[QdrantClient] = None,
    _embed_fn: Any = None,
) -> Union[list[dict], list[tuple[dict, float]]]:
    """Query the single Qdrant collection with the full indexed filter set.

    Builds a ``Filter(must=[...])`` conditionally: only supplied arguments produce
    a ``FieldCondition``.  A search is only permitted when at least ONE selective
    filter is supplied — see the selective-filter note below.

    Filter map (matches the indexed payload fields in setup_collection.py):
        source_type    → FieldCondition(key="source_type",    match=MatchValue(value=...))
        party_id       → FieldCondition(key="party_id",       match=MatchValue(value=...))
        region_path    → FieldCondition(key="region",         match=MatchAny(any=region_path))
                         Scalar region vs election_path list
        authority_tier → FieldCondition(key="authority_tier", match=MatchValue(value=...))
        publish_after  → FieldCondition(key="publish_date",   match=DatetimeRange(gte=...))

    Args:
        query:          Natural-language query string. Always required for context /
                        logging; used for embedding when ``query_vector`` is None.
        source_type:    Filter to a single content category
                        (Literal — not Python Enum).
                        One of: party_manifesto, vote_record, drucksache,
                        qa_transcript, parliamentary_speech.
                        Counts as a selective filter.
        party_id:       Tenant filter (short party slug, e.g. "spd"). Use for
                        single-owner chunks (manifestos); votes have no single
                        owner — use ``party_ids_contains`` instead.
                        Counts as a selective filter.
        party_ids_contains: Membership filter for vote_record chunks — returns
                        votes whose ``party_ids`` array contains this slug.
                        Counts as a selective filter.
        region_path:    Election region path list; chunks whose scalar ``region``
                        is a member of this list are returned (MatchAny).
                        NOT selective alone (requires party_id/party_ids_contains/
                        source_type to avoid a full-corpus scan).
        authority_tier: Filter by trustworthiness tier (Literal).
                        NOT selective alone.
        publish_after:  Return only chunks published on or after this datetime.
                        NOT selective alone.
        legislature_period_id: AW parliament_period ID (e.g. 161 for 21st Bundestag,
                        149 for Bayern 2023-2028). When set, restricts results to
                        chunks from that specific legislature. Globally unique integer
                        (state Wahlperiode numbers collide across states, so this AW
                        id is used instead). NOT selective alone.
        level:          Governance level of the election context
                        (``"federal"`` | ``"state"`` | ``"municipal"``).
                        When set to a NON-federal level AND
                        ``source_type="vote_record"``, triggers the
                        post-fetch tiered re-rank.
                        ``level="federal"`` and ``level=None`` both SKIP the
                        re-rank entirely — a federal election keeps federal votes
                        as primary content with no penalty:
                        fetches ``limit * _VOTE_CANDIDATE_MULTIPLIER`` candidates,
                        computes ``effective_score = point.score - penalty`` for each
                        (penalty=0.0 for local-region, SMALL for federal-tagged,
                        LARGE for federal-untagged), re-sorts and truncates to ``limit``.
                        Non-vote sources are unaffected.
        limit:          Maximum number of results (default 5).
        source:         Keyword-only provenance filter (e.g. ``"op"`` = only
                        video-bearing speeches), for explicit user-driven
                        scoping. NOT part of ``RetrieveSchema``, never set by
                        the default chat path (prefer-op dedup stays post-fetch
                        so un-scoped retrieval keeps its dip fallback). NOT
                        selective alone.
        publish_range:  Keyword-only bounded/strict ``publish_date`` window as a
                        single ``DatetimeRange`` — e.g. ``DatetimeRange(gte=t0, lte=t1)``
                        for a closed window or ``DatetimeRange(lt=t0)`` for a strict
                        cutoff. When set it emits ONE ``publish_date`` FieldCondition
                        carrying this exact range and the ``publish_after`` gte branch
                        is SKIPPED (publish_range wins; a debug line is logged if both
                        are supplied). This is a direct-caller / internal param only —
                        it is deliberately NOT part of ``RetrieveSchema`` (the Gemini
                        tool surface), so the untrusted-input attack surface is
                        unchanged. Bounds are expected to be tz-aware datetimes
                        produced by trusted internal callers (e.g. ``retrieve_two_pass``);
                        they are passed through unmodified without tz-normalisation.
                        NOT selective alone.
        query_vector:   Pre-computed embedding vector. When supplied, the embed
                        step is skipped entirely — ``_embed_fn`` / ``_get_embed()`` are
                        NOT called. Use this to embed once and reuse across multiple
                        retrieve() calls (single-party and comparison paths).
        score_threshold: Minimum cosine similarity for a result to be included.
                        When None (default), Qdrant returns results without a score
                        cutoff — identical to the default behaviour so existing
                        callers are unaffected.
        with_scores:    When False (default), return a plain ``list[dict]`` of
                        payloads — UNCHANGED behaviour, every existing caller is
                        unaffected. When True, return ``list[tuple[dict, float]]``
                        where the float is the ranking score retrieve() already
                        uses to order results: the ``effective_score`` (cosine
                        minus level penalty) in the down-rank branch, else the raw
                        ``point.score`` in the plain branch. Used by
                        ``retrieve_two_pass`` to apply recency decay on top of the
                        retrieve() ranking score.
        _client:        Optional QdrantClient override (for tests).
        _embed_fn:      Optional embed callable override (for tests without
                        a real OpenAI API key). Ignored when ``query_vector`` is
                        supplied.

    Returns:
        List of payload dicts for the matched points (with_payload=True).

    Raises:
        ValueError: If no selective filter (source_type, party_id, or
                    party_ids_contains) is supplied. The collection has no
                    global HNSW graph (m=0, payload_m=16): only a party_id
                    filter reaches a tenant HNSW sub-graph. party_ids_contains
                    and source_type restrict the candidate set through payload
                    indexes to a bounded filtered scan (the vote_record path
                    has no single tenant party, by design). Omitting all three
                    produces Filter(must=[]) — an unbounded scan of the whole
                    corpus, which is forbidden.
    """
    # Reject non-selective searches BEFORE embedding or touching the client.
    # There is NO global HNSW graph (m=0 / payload_m=16). What each accepted
    # filter buys:
    #   party_id           → tenant HNSW sub-graph (the fast path).
    #   party_ids_contains → payload-index-filtered scan; the designed
    #                        vote_record path (a vote has no single tenant
    #                        party), bounded to one party's votes.
    #   source_type        → payload-index-filtered scan bounded to one source
    #                        type; acceptable for internal callers that scope
    #                        further, NOT a tenant path.
    # region_path / authority_tier / publish_after alone are NOT accepted —
    # without one of the three filters above the search degrades to an
    # unbounded brute-force scan over the entire corpus.
    _is_selective = (
        source_type is not None
        or party_id is not None
        or party_ids_contains is not None
    )
    if not _is_selective:
        raise ValueError(
            "retrieve(): at least one selective filter is required — "
            "supply source_type, party_id, or party_ids_contains. "
            "The collection has no global HNSW graph (m=0 / payload_m=16), "
            "so omitting all three would brute-force the entire corpus "
            "(Filter(must=[]))."
        )

    client = _client if _client is not None else _get_qdrant()

    # Refuse to query a collection whose stored embedding-space fingerprint
    # contradicts the current configuration — scores against a foreign vector
    # space are garbage. Checked once per client per process (soft-pass for
    # fingerprint-less legacy stores and limited test doubles).
    if id(client) not in _fingerprint_checked_clients:
        check_fingerprint(client, COLLECTION_NAME)
        _fingerprint_checked_clients.add(id(client))

    # Build the filter must-clause list.
    must: list[FieldCondition] = []

    if source_type is not None:
        must.append(
            FieldCondition(key="source_type", match=MatchValue(value=source_type))
        )

    if party_id is not None:
        must.append(FieldCondition(key="party_id", match=MatchValue(value=party_id)))

    if source is not None:
        must.append(FieldCondition(key="source", match=MatchValue(value=source)))

    if party_ids_contains is not None:
        # Membership test on the party_ids array: a single MatchValue against an
        # array field matches when the value is an element ("did party X vote on
        # this motion"). Used for vote_record chunks (which have no single tenant
        # party_id) — see setup_collection.py party_ids index.
        must.append(
            FieldCondition(key="party_ids", match=MatchValue(value=party_ids_contains))
        )

    if region_path is not None:
        # Chunks store a scalar ``region``; the election provides a
        # list of ancestor regions.  MatchAny returns chunks whose region is
        # a member of the election's region_path.
        must.append(FieldCondition(key="region", match=MatchAny(any=region_path)))

    if authority_tier is not None:
        must.append(
            FieldCondition(key="authority_tier", match=MatchValue(value=authority_tier))
        )

    if publish_range is not None:
        # Bounded/strict publish_date window supplied directly by a trusted internal
        # caller (e.g. retrieve_two_pass). Emit exactly ONE publish_date condition with
        # this range and SKIP the publish_after gte branch — publish_range wins. Bounds
        # are assumed tz-aware (built by internal callers); passed through unmodified.
        if publish_after is not None:
            logger.debug(
                "retrieve(): both publish_after and publish_range supplied — "
                "publish_range wins, publish_after ignored."
            )
        must.append(FieldCondition(key="publish_date", range=publish_range))
    elif publish_after is not None:
        # The RetrieveSchema tool surface declares publish_after as an ISO string while
        # direct callers pass a datetime. Accept both — parse a string before the .tzinfo
        # access so an LLM-tool-driven call cannot crash here.
        gte_dt = (
            datetime.fromisoformat(publish_after)
            if isinstance(publish_after, str)
            else publish_after
        )
        # Ensure the datetime is timezone-aware (UTC) for Qdrant DatetimeRange.
        if gte_dt.tzinfo is None:
            gte_dt = gte_dt.replace(tzinfo=timezone.utc)
        must.append(
            FieldCondition(
                key="publish_date",
                range=DatetimeRange(gte=gte_dt),
            )
        )

    if legislature_period_id is not None:
        # AW parliament_period ID — narrows to a specific legislature.
        # NOT selective alone (needs source_type / party_id / party_ids_contains).
        must.append(
            FieldCondition(
                key="legislature_period_id",
                match=MatchValue(value=legislature_period_id),
            )
        )

    query_filter = Filter(must=must)

    # When query_vector is supplied, skip the embed step entirely.
    # This allows callers to embed once and reuse the vector across multiple
    # retrieve() calls (e.g. the single-party path: one embed for manifesto
    # + speech + vote retrievals).
    if query_vector is not None:
        # Use the caller-supplied pre-computed vector directly.
        vec = query_vector
    else:
        # Embed the query using the locked embedding model (shared helper).
        vec = _embed_query(query, _embed_fn)

    # Pass score_threshold to query_points only when not None.
    # When None (default), Qdrant returns results without a cutoff so existing
    # callers are unaffected.
    extra_kwargs: dict = {}
    if score_threshold is not None:
        extra_kwargs["score_threshold"] = score_threshold

    # The level-based soft down-rank applies ONLY to lower-level (non-federal)
    # elections. For a federal election, federal votes ARE the primary content —
    # no penalty, and no score_threshold distortion. level == "federal" therefore
    # behaves like the plain retrieval path. level is None (callers that don't
    # pass it) also skips the re-rank.
    _downrank_active = (
        level is not None and level != "federal" and source_type == "vote_record"
    )

    # The election's most specific region — e.g. "DE-BW" for a Baden-Württemberg
    # state election, "DE-BY-MUC" for a Munich municipal election, "DE" for federal.
    # Votes from this exact region are the local, primary content (no penalty); votes
    # from any broader region (federal "DE", or a parent state in a municipal election)
    # are down-ranked. This replaces a hardcoded region=="DE" check, which wrongly left
    # state votes un-penalised in a municipal election and other-state votes unpenalised.
    local_region = region_path[-1] if region_path else "DE"

    # Speech prefer-op dedup is a post-fetch pass (see below) that only touches
    # source_type == "parliamentary_speech". Like the vote down-rank it never adds a
    # Qdrant `source` filter — the down-rank and two-pass paths stay unchanged.
    _speech_dedup_active = source_type == "parliamentary_speech"

    # Over-fetch when the re-rank is active so a genuinely-relevant local vote ranked
    # below the top-N by RAW cosine still enters the pool and can be promoted after the
    # federal penalty is applied. Floor the pool so small `limit`s don't starve it.
    # For speeches, over-fetch so the prefer-op dedup collapse (dip+op → op) doesn't
    # shrink the returned bucket below `limit`.
    if _downrank_active:
        fetch_limit = max(limit * _VOTE_CANDIDATE_MULTIPLIER, _VOTE_CANDIDATE_FLOOR)
    elif _speech_dedup_active:
        fetch_limit = max(limit * _SPEECH_CANDIDATE_MULTIPLIER, _SPEECH_CANDIDATE_FLOOR)
    else:
        fetch_limit = limit

    # query_points with named vector "dense" (REQUIRED — collection uses named vectors).
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vec,
        using="dense",
        query_filter=query_filter,
        limit=fetch_limit,
        with_payload=True,
        **extra_kwargs,
    )

    # Post-fetch vote-level re-rank.
    # Guard: only active for a non-federal election AND source_type vote_record.
    # Manifesto/speech calls are byte-for-byte unaffected (source_type != "vote_record").
    if _downrank_active:
        ranked: list[tuple[dict, float]] = []
        for point in results.points:
            if point.payload is None:
                continue
            payload_region = point.payload.get("region", "")
            if payload_region == local_region:
                # Local vote (same region as the election) — primary content, no penalty.
                penalty = 0.0
            else:
                # Broader-region vote (federal "DE", or a parent level in a municipal
                # election). Down-rank by relevance: SMALL if this election's level is in
                # the vote's relevance_levels, LARGE otherwise. Max-recall default:
                # relevance_levels missing → treat as ALL_LEVELS so legacy/untagged chunks
                # get the small penalty at most (never buried entirely).
                rel_levels = point.payload.get("relevance_levels") or sorted(ALL_LEVELS)
                penalty = (
                    _VOTE_DOWNRANK_SMALL
                    if level in rel_levels
                    else _VOTE_DOWNRANK_LARGE
                )
            # Penalise the RANKING score only. Do NOT re-apply score_threshold to the
            # penalised score: Qdrant already enforced the cutoff on the true cosine
            # similarity, and the penalty is a ranking device, not a relevance signal.
            # Re-thresholding here would DROP relevant broader-region votes instead of
            # merely lowering them — defeating the "keep, but rank below local" contract.
            effective_score = point.score - penalty
            ranked.append((point.payload, effective_score))
        ranked.sort(key=lambda x: x[1], reverse=True)
        top = ranked[:limit]
        if with_scores:
            return top
        return [payload for payload, _ in top]

    plain = [point for point in results.points if point.payload is not None]

    # Post-fetch prefer-op dedup — ONLY for parliamentary_speech.
    # Collapse dip+op duplicates on speech_key (keep the video-bearing op member),
    # then truncate to `limit`. The over-fetch above kept the pool large enough that
    # the collapse does not shrink the bucket below `limit`. Runs per-bucket because
    # retrieve_two_pass calls retrieve() once per (current/historic) pass.
    # `plain` filtered out None payloads above, but mypy can't carry that narrowing
    # through attribute access — cast each payload back to dict.
    if _speech_dedup_active:
        score_by_id = {id(point.payload): point.score for point in plain}
        deduped = dedup_prefer_op([cast(dict, point.payload) for point in plain])[
            :limit
        ]
        if with_scores:
            return [(payload, score_by_id[id(payload)]) for payload in deduped]
        return deduped

    if with_scores:
        return [(cast(dict, point.payload), point.score) for point in plain]
    return [cast(dict, point.payload) for point in plain]


# ---------------------------------------------------------------------------
# retrieve_two_pass() — temporal current-vs-historic split over publish_date
#
# Runs two retrieve() passes keyed on the cross-source ``publish_date`` field and
# returns labelled ``{"current": [...], "historic": [...]}`` buckets:
#   - current pass  : publish_date ∈ [term_start, term_end], FLAT (no time
#                     weighting inside the window — a term's whole record is
#                     equally relevant). legislature_period_id is forwarded here.
#   - historic pass : publish_date < term_start, gated by a HIGH
#                     historic_score_threshold so only strongly on-topic history
#                     returns. legislature_period_id is forced to None (a
#                     single-period filter would hard-exclude every prior-term vote
#                     and empty the bucket).
# The gte/lt boundary at term_start means current owns term_start and historic is
# strictly before it — no overlap, no gap. ONE query vector is embedded once here
# and reused across both passes (no extra embedding). The level down-rank
# and the no-re-threshold guarantee are INHERITED from retrieve() — this
# function does NOT re-implement penalty logic.
# ---------------------------------------------------------------------------


def retrieve_two_pass(
    query: str,
    *,
    term_start: datetime,
    term_end: datetime,
    source_type: Optional[SourceTypeLiteral] = None,
    party_id: Optional[str] = None,
    party_ids_contains: Optional[str] = None,
    source: Optional[SourceLiteral] = None,
    region_path: Optional[list[str]] = None,
    level: Optional[str] = None,
    legislature_period_id: Optional[int] = None,
    current_limit: int = 5,
    historic_limit: int = 2,
    current_score_threshold: Optional[float] = None,
    historic_score_threshold: float,
    query_vector: Optional[list[float]] = None,
    _client: Optional[QdrantClient] = None,
    _embed_fn: Any = None,
) -> dict[str, list[dict]]:
    """Two-pass temporal retrieval returning ``{"current", "historic"}`` buckets.

    See the module comment above for the full rationale.

    Args:
        query:          Natural-language query string.
        term_start:     Inclusive lower bound of the current term window
                        (tz-aware datetime). Owned by the current pass; the
                        historic pass is strictly before it.
        term_end:       Inclusive upper bound of the current term window
                        (tz-aware datetime).
        source_type:    Content category filter (see retrieve()). Selective.
        party_id:       Tenant filter (see retrieve()). Selective.
        party_ids_contains: Vote membership filter (see retrieve()). Selective.
        source:         Provenance filter (see retrieve()); forwarded to both passes.
        region_path:    Election region path (MatchAny). Forwarded to both passes.
        level:          Governance level; forwarded to both passes so the
                        vote-level down-rank composes WITHIN each pass.
        legislature_period_id: AW parliament_period ID. Forwarded to the CURRENT
                        pass ONLY; the historic pass receives None.
        current_limit:  Max results in the current bucket (default 5).
        historic_limit: Max results in the historic bucket (default 2 — keep the
                        historic context small). The historic pass over-fetches an
                        enlarged pool, applies an exponential recency decay anchored
                        at term_start (half-life _HISTORIC_DECAY_HALFLIFE_DAYS), then
                        truncates to this limit.
        current_score_threshold: Optional cosine cutoff for the current pass.
        historic_score_threshold: REQUIRED high cosine cutoff for the historic
                        pass — the "only super-relevant facts make it" knob.
        query_vector:   Pre-computed embedding. When None, the query is embedded
                        ONCE here and the same vector is passed to both passes.
        _client:        Optional QdrantClient override (for tests).
        _embed_fn:      Optional embed callable override (for tests).

    Returns:
        ``{"current": [...payloads...], "historic": [...payloads...]}``.
    """
    # (1) Embed once and reuse across BOTH passes — single-embed reuse is mandatory
    # (one query vector reused across both passes, no extra embedding).
    vec = query_vector if query_vector is not None else _embed_query(query, _embed_fn)

    # (2) current pass — bounded [term_start, term_end], flat, level + period forwarded.
    current_results = retrieve(
        query,
        source_type=source_type,
        party_id=party_id,
        party_ids_contains=party_ids_contains,
        source=source,
        region_path=region_path,
        legislature_period_id=legislature_period_id,
        level=level,
        limit=current_limit,
        publish_range=DatetimeRange(gte=term_start, lte=term_end),
        query_vector=vec,
        score_threshold=current_score_threshold,
        _client=_client,
    )

    # (3) historic pass — strictly before term_start, high threshold, NO period filter,
    # then an exponential recency decay anchored at term_start so that within the
    # (possibly multi-period) history more-recent material outranks older material at
    # equal cosine. The threshold gate stays on the RAW cosine (enforced by retrieve()):
    # decay is a ranking device only, never a relevance cutoff. We over-fetch an enlarged
    # pool, decay-re-rank it, then truncate to historic_limit.
    historic_pool_limit = max(historic_limit * 10, 20)
    historic_scored = retrieve(
        query,
        source_type=source_type,
        party_id=party_id,
        party_ids_contains=party_ids_contains,
        source=source,
        region_path=region_path,
        legislature_period_id=None,
        level=level,
        limit=historic_pool_limit,
        publish_range=DatetimeRange(lt=term_start),
        query_vector=vec,
        score_threshold=historic_score_threshold,
        with_scores=True,
        _client=_client,
    )

    term_start_date = term_start.date()
    decayed: list[tuple[dict, float]] = []
    for payload, score in historic_scored:
        pub_date = _parse_publish_date(payload.get("publish_date"))
        if pub_date is None:
            # Missing / unparseable publish_date → no recency penalty, never crash.
            decay = 1.0
        else:
            age_days = max(0, (term_start_date - pub_date).days)
            decay = 0.5 ** (age_days / _HISTORIC_DECAY_HALFLIFE_DAYS)
        # Clamp at 0 — a vote-downranked NEGATIVE score times a small decay
        # would rank an older item ABOVE a newer one (multiplying a negative by
        # <1 raises it), inverting the recency ordering.
        decayed.append((payload, max(score, 0.0) * decay))
    # Stable sort by decayed score desc — equal decayed scores keep retrieve() order.
    decayed.sort(key=lambda x: x[1], reverse=True)
    historic_results = [payload for payload, _ in decayed[:historic_limit]]

    # (4) Labelled buckets. The level down-rank and the no-re-threshold guarantee
    # are inherited from retrieve() — not re-implemented here. The current bucket stays
    # flat (no decay); only the historic bucket is recency-weighted.
    # current pass runs with_scores=False → list[dict]; narrow the union for the
    # dict[str, list[dict]] return contract.
    return {"current": cast(list[dict], current_results), "historic": historic_results}


# ---------------------------------------------------------------------------
# Gemini tool declaration (bind_tools surface, standalone)
# ---------------------------------------------------------------------------


class RetrieveSchema(BaseModel):
    """Pydantic schema for the Gemini ``retrieve`` tool declaration.

    Use ``llm.bind_tools([RetrieveSchema])`` to register this as a Gemini
    function-calling tool.  All enum-constrained args are ``Literal[...]``
    (not Python Enum) to avoid langchain-google-genai issue #409.

    Election-scope parameters the model cannot know or should not choose
    (authority_tier, legislature_period_id, wahlperiode) are deliberately NOT
    exposed here — the server supplies them from the election context. This is
    therefore a curated subset of ``retrieve()``'s parameters, not a 1:1 mirror.
    """

    query: str = Field(
        ..., description="Natural-language query to retrieve relevant chunks for."
    )
    source_type: Optional[SourceTypeLiteral] = Field(
        None,
        description=(
            "Content category filter. One of: party_manifesto, vote_record, "
            "drucksache, qa_transcript, parliamentary_speech. "
            "REQUIRED unless party_id or party_ids_contains is set. "
            "The collection uses tenant-only HNSW (m=0) — every retrieval MUST "
            "supply at least one of source_type, party_id, or party_ids_contains; "
            "omitting all three is rejected (brute-force scan forbidden)."
        ),
    )
    party_id: Optional[str] = Field(
        None,
        description=(
            "Party tenant filter (short slug, e.g. 'spd'). "
            "REQUIRED unless source_type or party_ids_contains is set. "
            "Every retrieval MUST supply at least one of source_type, party_id, or "
            "party_ids_contains — the store is tenant-partitioned (m=0 HNSW) and "
            "omitting all three triggers a brute-force scan that is rejected."
        ),
    )
    party_ids_contains: Optional[str] = Field(
        None,
        description=(
            "Membership filter for vote records (short slug, e.g. 'spd'): returns "
            "votes whose party_ids array contains this party. Use for vote_record "
            "queries instead of party_id (votes have no single tenant owner). "
            "Counts as a selective filter — satisfies the requirement that at least "
            "one of source_type, party_id, or party_ids_contains must be set."
        ),
    )
    region_path: Optional[list[str]] = Field(
        None,
        description=(
            "Election region path list (e.g. ['EU', 'DE']). Chunks whose scalar "
            "region is a member of this list are returned (MatchAny)."
        ),
    )
    publish_after: Optional[str] = Field(
        None,
        description=(
            "ISO 8601 datetime string (e.g. '2024-01-01T00:00:00Z'). "
            "Only return chunks published on or after this datetime."
        ),
    )
    limit: int = Field(
        5, description="Maximum number of results to return (default 5)."
    )


def get_gemini_tool_binding(llm: Any) -> Any:
    """Return the Gemini LLM with the retrieve tool bound.

    Usage::

        from src.llms import google_gemini_2_5_flash
        from src.retrieve import get_gemini_tool_binding

        llm_with_tools = get_gemini_tool_binding(google_gemini_2_5_flash)

    The tool declaration is standalone — this does NOT import or modify
    chat_service or vector_store_helper.

    Args:
        llm: A ChatGoogleGenerativeAI instance (e.g. ``google_gemini_2_5_flash``).

    Returns:
        The LLM with the ``retrieve`` tool bound via ``bind_tools([RetrieveSchema])``.
    """
    return llm.bind_tools([RetrieveSchema])
