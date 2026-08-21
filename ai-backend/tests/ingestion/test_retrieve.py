# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for post-fetch vote-level re-rank in retrieve().

Test coverage:
  - test_downrank_defense_state_election: defense vote in state election
    context surfaces above federal-procedural vote after penalty.
  - test_downrank_local_leads: same cosine score; local-region chunk beats federal.
  - test_no_downrank_manifesto: manifesto retrieve with level set must
    NOT apply the re-rank (source_type != "vote_record").
  - test_penalty_tiers: three penalty tiers produce the correct effective ordering.

All tests use mocked QdrantClient (no live Qdrant required) via `_client` injection
and `query_vector` injection (no embedding API call).  Qdrant point objects are
simulated via types.SimpleNamespace.
"""

from __future__ import annotations

import types
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from qdrant_client.models import DatetimeRange

from src.ingestion.retrieve import retrieve, retrieve_two_pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_point(
    score: float,
    region: str,
    relevance_levels: list[str] | None,
    source_type: str = "vote_record",
    party_id: str = "spd",
) -> types.SimpleNamespace:
    """Return a SimpleNamespace simulating a Qdrant ScoredPoint.

    Attributes:
        score:   cosine similarity (float, as returned by query_points).
        payload: dict with fields retrieve() reads for re-rank and return.
    """
    return types.SimpleNamespace(
        score=score,
        payload={
            "source_type": source_type,
            "party_id": party_id,
            "region": region,
            "relevance_levels": relevance_levels,
            "text": f"Mock chunk region={region} source_type={source_type}",
            "chunk_index": 0,
            "chunk_key": f"mock:{region}:0000",
            "source_item_id": "00000000-0000-0000-0000-000000000001",
            "citation_url": None,
            "citation_title": None,
            "authority_tier": "factual_record",
            "publish_date": "2024-01-15T00:00:00",
        },
    )


def _make_mock_client(points: list[types.SimpleNamespace]) -> MagicMock:
    """Return a mock QdrantClient whose query_points returns the given points."""
    mock_client = MagicMock()
    query_result = MagicMock()
    query_result.points = points
    mock_client.query_points.return_value = query_result
    return mock_client


_ZERO_VECTOR = [0.0] * 3072  # matches EMBEDDING_DIM


# ---------------------------------------------------------------------------
# test_downrank_defense_state_election
#
# State-level election with level="state".
# Three points simulating a Bavarian election query:
#   Point A: region=DE-BY, relevance_levels=[federal,state], score=0.72
#            → local-region, penalty=0.0,  effective_score=0.72
#   Point B: region=DE,    relevance_levels=[federal,state], score=0.70
#            → federal + tagged, penalty=0.05, effective_score=0.65
#   Point C: region=DE,    relevance_levels=[federal],       score=0.68
#            → federal + NOT tagged for state, penalty=0.20, effective_score=0.48
#
# Expected order: A first (local), B second (defense-tagged federal), C dropped or last.
# ---------------------------------------------------------------------------


def test_downrank_defense_state_election() -> None:
    """Defense-tagged federal vote ranks above non-state-tagged federal vote.

    Mock three Qdrant points with scores 0.72/0.70/0.68.
    After state-level penalty:
      - DE-BY chunk (local) stays at 0.72.
      - DE defense-tagged chunk: 0.70 - 0.05 = 0.65.
      - DE non-state chunk:      0.68 - 0.20 = 0.48.
    Top-2 must be [DE-BY, DE-defense]; the DE-only chunk is dropped or last.
    """
    point_a = _make_point(0.72, "DE-BY", ["federal", "state"])
    point_b = _make_point(0.70, "DE", ["federal", "state"])
    point_c = _make_point(0.68, "DE", ["federal"])

    mock_client = _make_mock_client([point_a, point_b, point_c])

    results = retrieve(
        query="Verteidigung Bayern",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],  # Bavarian state election → local region DE-BY
        level="state",  # type: ignore[call-arg]
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        limit=2,
    )

    assert len(results) == 2, f"Expected 2 results (limit), got {len(results)}"
    assert results[0]["region"] == "DE-BY", (
        f"Local DE-BY chunk must be first; got region={results[0].get('region')!r}"
    )
    assert results[1]["region"] == "DE", (
        f"Defense-tagged federal chunk must be second; got region={results[1].get('region')!r}"
    )
    assert results[1].get("relevance_levels") == ["federal", "state"], (
        "Second result must be the state-tagged federal chunk, not the non-tagged one"
    )


def test_no_downrank_federal_election() -> None:
    """A federal election (level="federal") applies NO penalty.

    Federal votes are the primary content of a federal election, so the re-rank
    must be skipped entirely — no penalty AND no score_threshold distortion. A
    federal vote scoring just above threshold (0.52) must survive; under the bug
    it would become 0.52 - 0.05 = 0.47 and be dropped by the re-applied threshold.
    """
    point_a = _make_point(0.52, "DE", ["federal"])
    point_b = _make_point(0.70, "DE", ["federal", "state"])
    mock_client = _make_mock_client([point_b, point_a])

    results = retrieve(
        query="Verteidigung",
        source_type="vote_record",
        level="federal",
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        score_threshold=0.5,
        limit=5,
    )

    regions_scores = [(r.get("region"), r.get("relevance_levels")) for r in results]
    assert len(results) == 2, (
        f"Federal election must keep both federal votes (no penalty drop), got {regions_scores!r}"
    )


def test_downrank_keeps_federal_vote_above_threshold_in_state_election() -> None:
    """In a STATE election, a federal vote just above score_threshold must be KEPT
    (ranked below the local vote), NOT dropped by re-thresholding the penalised score.

    Federal-only vote scores 0.52 (> threshold 0.5); LARGE penalty 0.20 → effective 0.32.
    The prior code re-applied the 0.5 threshold to 0.32 and dropped the vote entirely,
    defeating the "keep federal votes but rank them below local" contract.
    """
    point_local = _make_point(0.60, "DE-BY", ["federal", "state"])
    point_federal = _make_point(0.52, "DE", ["federal"])  # federal-only → LARGE penalty
    mock_client = _make_mock_client([point_local, point_federal])

    results = retrieve(
        query="Außenpolitik",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        level="state",  # type: ignore[call-arg]
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        score_threshold=0.5,
        limit=5,
    )

    regions = [r.get("region") for r in results]
    assert regions == ["DE-BY", "DE"], (
        f"Federal vote above threshold must be kept and ranked below local; got {regions!r}"
    )


# ---------------------------------------------------------------------------
# test_downrank_local_leads
#
# Tie-break: two chunks with identical cosine score.
# The local (DE-BY) chunk must outrank the federal (DE) chunk because
# penalty for local = 0.0 and for federal = 0.05 (small penalty, tagged).
# ---------------------------------------------------------------------------


def test_downrank_local_leads() -> None:
    """Same cosine score: local-region chunk must outrank federal chunk (penalty 0.0 < 0.05).

    Verifies that the penalty tiebreaker works when cosine scores are equal.
    """
    # Both have the same score. The local chunk must lead.
    point_local = _make_point(0.65, "DE-BY", ["federal", "state"])
    point_federal = _make_point(0.65, "DE", ["federal", "state"])

    mock_client = _make_mock_client(
        [point_federal, point_local]
    )  # federal first in Qdrant

    results = retrieve(
        query="Haushalt Bayern",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],  # Bavarian state election → local region DE-BY
        level="state",  # type: ignore[call-arg]
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        limit=2,
    )

    assert len(results) >= 2, f"Expected ≥2 results, got {len(results)}"
    assert results[0]["region"] == "DE-BY", (
        f"Local chunk must lead after penalty (0.0 < 0.05); got {results[0].get('region')!r}"
    )


# ---------------------------------------------------------------------------
# test_no_downrank_manifesto
#
# When source_type != "vote_record", the re-rank branch must
# NOT fire — manifesto/speech retrieve results are returned in Qdrant order.
# ---------------------------------------------------------------------------


def test_no_downrank_manifesto() -> None:
    """Manifesto retrieve with level set must not trigger vote re-rank.

    Qdrant returns manifesto points in order [A, B].
    After calling retrieve(source_type='party_manifesto', level='state', ...),
    results must be in the original Qdrant order (no penalty applied).
    """
    point_a = _make_point(0.72, "DE", None, source_type="party_manifesto")
    point_b = _make_point(0.68, "DE", None, source_type="party_manifesto")

    mock_client = _make_mock_client([point_a, point_b])

    results = retrieve(
        query="Bildungspolitik",
        source_type="party_manifesto",
        level="state",  # type: ignore[call-arg]
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        limit=5,
    )

    # Manifesto results must be unchanged from Qdrant order.
    # The re-rank guard `if source_type == "vote_record"` ensures
    # manifesto calls skip the penalty entirely.
    assert len(results) == 2, f"Expected 2 manifesto results, got {len(results)}"
    assert results[0]["source_type"] == "party_manifesto"
    assert results[1]["source_type"] == "party_manifesto"
    # Scores must be in Qdrant order (no re-rank): first result must be point_a's payload.
    assert (
        results[0]
        .get("text", "")
        .startswith("Mock chunk region=DE source_type=party_manifesto")
    ), "manifesto results must not be re-ranked by vote penalty logic"


# ---------------------------------------------------------------------------
# test_penalty_tiers
#
# Verifies all three penalty tiers produce correct effective ordering:
#   Tier 1: local region → penalty 0.0
#   Tier 2: federal + level in relevance_levels → penalty SMALL (0.05)
#   Tier 3: federal + level NOT in relevance_levels → penalty LARGE (0.20)
#
# Also verifies relevance_levels=None on a federal chunk is treated as ALL_LEVELS
# (max-recall), giving penalty SMALL (since "state" is in ALL_LEVELS).
# ---------------------------------------------------------------------------


def test_penalty_tiers() -> None:
    """Three penalty tiers: local=0.0, federal-tagged=SMALL, federal-untagged=LARGE.

    Mock federal DE votes with:
      - relevance_levels=[federal,state] → Tier 2 (small penalty, level 'state' present)
      - relevance_levels=[federal]       → Tier 3 (large penalty, 'state' absent)
      - relevance_levels=None            → max-recall → treated as ALL_LEVELS
                                           → Tier 2 (small penalty; 'state' in ALL_LEVELS)

    All have the same cosine score to isolate penalty effect.
    """
    # All same score; ordering determined purely by penalty tier.
    point_tier2_tagged = _make_point(0.70, "DE", ["federal", "state"])
    point_tier3_untagged = _make_point(0.70, "DE", ["federal"])
    point_tier2_null = _make_point(0.70, "DE", None)  # None → small penalty

    mock_client = _make_mock_client(
        [
            point_tier3_untagged,  # worst order in Qdrant
            point_tier2_null,
            point_tier2_tagged,
        ]
    )

    results = retrieve(
        query="Haushalt",
        source_type="vote_record",
        region_path=[
            "DE",
            "DE-BY",
        ],  # state election → local region DE-BY (all mocks are federal DE)
        level="state",  # type: ignore[call-arg]
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        limit=3,
    )

    assert len(results) == 3, f"Expected 3 results, got {len(results)}"

    # tier3 (large penalty 0.20) must be last.
    assert results[-1].get("relevance_levels") == ["federal"], (
        "Federal-only (Tier 3 large penalty) must rank last"
    )

    # tier2 chunks (small penalty 0.05) must both be ahead of tier3.
    assert results[0].get("relevance_levels") in (["federal", "state"], None), (
        "First result must be a Tier-2 chunk (small penalty)"
    )
    assert results[1].get("relevance_levels") in (["federal", "state"], None), (
        "Second result must be a Tier-2 chunk (small penalty)"
    )


# ---------------------------------------------------------------------------
# publish_range passthrough on retrieve()
#
# retrieve(publish_range=DatetimeRange(...)) must build a SINGLE publish_date
# FieldCondition carrying that exact range (bounded [gte, lte] window or strict
# lt cutoff). When both publish_after and publish_range are supplied,
# publish_range wins and publish_after is ignored. publish_range=None leaves the
# existing publish_after path byte-for-byte unchanged.
# ---------------------------------------------------------------------------


def _publish_date_conditions(mock_client: MagicMock) -> list:
    """Return every publish_date FieldCondition from the captured query_filter."""
    query_filter = mock_client.query_points.call_args.kwargs["query_filter"]
    return [c for c in query_filter.must if getattr(c, "key", None) == "publish_date"]


def test_publish_range_bounded_window_builds_single_condition() -> None:
    """publish_range=DatetimeRange(gte, lte) → one publish_date condition, exact bounds."""
    t0 = datetime(2021, 3, 14, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 14, tzinfo=timezone.utc)
    mock_client = _make_mock_client([])

    retrieve(
        query="Haushalt",
        source_type="vote_record",
        publish_range=DatetimeRange(gte=t0, lte=t1),
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    conds = _publish_date_conditions(mock_client)
    assert len(conds) == 1, (
        f"Expected exactly one publish_date condition, got {len(conds)}"
    )
    assert conds[0].range.gte == t0
    assert conds[0].range.lte == t1
    assert conds[0].range.lt is None
    assert conds[0].range.gt is None


def test_publish_range_strict_cutoff_builds_lt_condition() -> None:
    """publish_range=DatetimeRange(lt) → a strict lower-cutoff publish_date condition."""
    t0 = datetime(2021, 3, 14, tzinfo=timezone.utc)
    mock_client = _make_mock_client([])

    retrieve(
        query="Haushalt",
        source_type="vote_record",
        publish_range=DatetimeRange(lt=t0),
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    conds = _publish_date_conditions(mock_client)
    assert len(conds) == 1, (
        f"Expected exactly one publish_date condition, got {len(conds)}"
    )
    assert conds[0].range.lt == t0
    assert conds[0].range.gte is None
    assert conds[0].range.lte is None


def test_publish_range_wins_over_publish_after() -> None:
    """When both are supplied, publish_range wins and publish_after is ignored.

    Only ONE publish_date condition is emitted and it carries the publish_range
    bounds — the publish_after gte is not applied.
    """
    after = datetime(2010, 1, 1, tzinfo=timezone.utc)
    t0 = datetime(2021, 3, 14, tzinfo=timezone.utc)
    t1 = datetime(2026, 3, 14, tzinfo=timezone.utc)
    mock_client = _make_mock_client([])

    retrieve(
        query="Haushalt",
        source_type="vote_record",
        publish_after=after,
        publish_range=DatetimeRange(gte=t0, lte=t1),
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    conds = _publish_date_conditions(mock_client)
    assert len(conds) == 1, (
        f"publish_range must replace publish_after (one condition), got {len(conds)}"
    )
    assert conds[0].range.gte == t0, "publish_range gte must win over publish_after"
    assert conds[0].range.lte == t1


def test_publish_range_none_preserves_publish_after() -> None:
    """publish_range=None leaves the existing publish_after gte path unchanged."""
    after = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_client = _make_mock_client([])

    retrieve(
        query="Haushalt",
        source_type="vote_record",
        publish_after=after,
        publish_range=None,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    conds = _publish_date_conditions(mock_client)
    assert len(conds) == 1, f"Expected one publish_date condition, got {len(conds)}"
    assert conds[0].range.gte == after
    assert conds[0].range.lt is None
    assert conds[0].range.lte is None


# ---------------------------------------------------------------------------
# retrieve_two_pass() → {current, historic} buckets
#
# current pass  = publish_date ∈ [term_start, term_end], flat, level-forwarded.
# historic pass = publish_date < term_start, gated by a HIGH score_threshold,
#                 legislature_period_id forced to None.
# One query vector is embedded once and reused across both passes.
# The level down-rank runs WITHIN each pass (ranked, not re-thresholded).
# ---------------------------------------------------------------------------


def _make_two_pass_client(
    current_points: list[types.SimpleNamespace],
    historic_points: list[types.SimpleNamespace],
) -> MagicMock:
    """Return a mock client whose query_points yields current then historic results.

    retrieve_two_pass runs the current pass first, then the historic pass, so the
    side_effect order mirrors that call order.
    """
    mock_client = MagicMock()
    cur_result = MagicMock()
    cur_result.points = current_points
    hist_result = MagicMock()
    hist_result.points = historic_points
    mock_client.query_points.side_effect = [cur_result, hist_result]
    return mock_client


_TERM_START = datetime(2021, 3, 14, tzinfo=timezone.utc)
_TERM_END = datetime(2026, 3, 14, tzinfo=timezone.utc)


def _filter_keys(call) -> list:
    """Return the FieldCondition keys of a captured query_points call's filter."""
    return [getattr(c, "key", None) for c in call.kwargs["query_filter"].must]


def _publish_date_range(call):
    """Return the DatetimeRange of the publish_date condition in a captured call."""
    for c in call.kwargs["query_filter"].must:
        if getattr(c, "key", None) == "publish_date":
            return c.range
    return None


def test_two_pass_split_by_publish_date() -> None:
    """current bucket = in-window points; historic bucket = pre-window points.

    Also verifies each pass builds the correct publish_date window: current is a
    bounded [term_start, term_end] and historic is a strict lt term_start.
    """
    in_window = _make_point(0.70, "DE-BY", ["state"], party_id="in")
    pre_window = _make_point(0.65, "DE-BY", ["state"], party_id="pre")
    mock_client = _make_two_pass_client([in_window], [pre_window])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert set(buckets) == {"current", "historic"}
    assert [p["party_id"] for p in buckets["current"]] == ["in"]
    assert [p["party_id"] for p in buckets["historic"]] == ["pre"]

    cur_call, hist_call = mock_client.query_points.call_args_list
    cur_range = _publish_date_range(cur_call)
    assert cur_range.gte == _TERM_START and cur_range.lte == _TERM_END
    assert cur_range.lt is None
    hist_range = _publish_date_range(hist_call)
    assert hist_range.lt == _TERM_START
    assert hist_range.gte is None and hist_range.lte is None


def test_two_pass_current_is_flat() -> None:
    """current pass applies NO recency weighting: equal-cosine, equal-region points
    keep their original Qdrant order."""
    first = _make_point(0.70, "DE-BY", ["state"], party_id="first")
    second = _make_point(0.70, "DE-BY", ["state"], party_id="second")
    mock_client = _make_two_pass_client([first, second], [])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert [p["party_id"] for p in buckets["current"]] == ["first", "second"], (
        "current bucket must preserve Qdrant order (flat — no time weighting)"
    )


def test_two_pass_historic_high_threshold() -> None:
    """current_score_threshold forwards to the current pass; historic_score_threshold
    forwards to the historic pass."""
    mock_client = _make_two_pass_client([], [])

    retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        current_score_threshold=0.30,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    cur_call, hist_call = mock_client.query_points.call_args_list
    assert cur_call.kwargs["score_threshold"] == 0.30
    assert hist_call.kwargs["score_threshold"] == 0.60


def test_two_pass_historic_omits_legislature_period_id() -> None:
    """legislature_period_id is forwarded to the CURRENT pass only; the historic pass
    receives None (so a single-period filter can't empty the historic bucket)."""
    mock_client = _make_two_pass_client([], [])

    retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        legislature_period_id=161,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    cur_call, hist_call = mock_client.query_points.call_args_list
    assert "legislature_period_id" in _filter_keys(cur_call), (
        "current pass must carry the legislature_period_id filter"
    )
    assert "legislature_period_id" not in _filter_keys(hist_call), (
        "historic pass must NOT carry legislature_period_id (would empty the bucket)"
    )


def test_two_pass_single_embed_reuse() -> None:
    """When query_vector is None, embed exactly once and reuse the SAME vector for
    both passes."""
    calls = {"n": 0}

    def spy_embed(_query: str) -> list[float]:
        calls["n"] += 1
        return _ZERO_VECTOR

    mock_client = _make_two_pass_client([], [])

    retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_score_threshold=0.60,
        query_vector=None,
        _client=mock_client,
        _embed_fn=spy_embed,
    )

    assert calls["n"] == 1, f"Expected exactly one embed call, got {calls['n']}"
    cur_call, hist_call = mock_client.query_points.call_args_list
    assert cur_call.kwargs["query"] is hist_call.kwargs["query"], (
        "both passes must reuse the identical query vector object"
    )


def test_two_pass_no_drop_combined_penalty() -> None:
    """REGRESSION: in the historic pass a federal-only vote above the HIGH historic
    threshold survives the LARGE level penalty — ranked below local, NOT dropped by
    re-thresholding the penalised score.

    Historic pass, level='state', region ['DE','DE-BY'], historic threshold 0.60.
    local DE-BY vote 0.65 (penalty 0.0) and federal-only DE vote 0.62 (> 0.60, LARGE
    penalty 0.20 → 0.42). The federal vote must stay, ranked after local.
    """
    local = _make_point(0.65, "DE-BY", ["federal", "state"])
    federal = _make_point(0.62, "DE", ["federal"])  # federal-only → LARGE penalty
    mock_client = _make_two_pass_client([], [local, federal])

    buckets = retrieve_two_pass(
        "Außenpolitik",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        level="state",  # type: ignore[call-arg]
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    regions = [p["region"] for p in buckets["historic"]]
    assert regions == ["DE-BY", "DE"], (
        f"historic federal vote above threshold must be kept and ranked below local; "
        f"got {regions!r}"
    )


# ---------------------------------------------------------------------------
# with_scores=True — retrieve() returns (payload, score) tuples.
# Default (with_scores=False) is UNCHANGED (plain list[dict]).
# ---------------------------------------------------------------------------


def test_with_scores_true_returns_payload_score_tuples() -> None:
    """with_scores=True → list[(payload, score)] using the plain-branch point.score."""
    point = _make_point(0.71, "DE-BY", ["state"])
    mock_client = _make_mock_client([point])

    res = retrieve(
        "Haushalt",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        with_scores=True,
    )

    assert isinstance(res[0], tuple) and len(res[0]) == 2
    payload, score = res[0]
    assert isinstance(payload, dict)
    assert score == pytest.approx(0.71)


def test_with_scores_false_default_returns_payloads() -> None:
    """Default with_scores=False is unchanged — a plain list of payload dicts."""
    point = _make_point(0.71, "DE-BY", ["state"])
    mock_client = _make_mock_client([point])

    res = retrieve(
        "Haushalt",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert isinstance(res[0], dict)
    assert res[0]["region"] == "DE-BY"


def test_with_scores_true_downrank_branch_returns_effective_score() -> None:
    """In the level down-rank branch, with_scores=True returns the effective_score
    (cosine minus penalty), NOT the raw cosine."""
    # Federal-only vote in a state election → LARGE penalty 0.20 → effective 0.50.
    federal = _make_point(0.70, "DE", ["federal"])
    mock_client = _make_mock_client([federal])

    res = retrieve(
        "Außenpolitik",
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        level="state",
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
        with_scores=True,
    )

    _payload, score = res[0]
    assert score == pytest.approx(0.50), (
        "expected effective_score = 0.70 - 0.20 (LARGE penalty)"
    )


# ---------------------------------------------------------------------------
# Historic recency decay — the historic bucket is recency-weighted (anchored at
# term_start), while the current bucket stays flat.
# ---------------------------------------------------------------------------


def _dated_point(
    score: float,
    publish_date: str,
    party_id: str,
    region: str = "DE-BY",
    relevance_levels: list[str] | None = None,
) -> types.SimpleNamespace:
    """A vote point with an explicit publish_date (overrides the helper default)."""
    point = _make_point(
        score,
        region,
        relevance_levels if relevance_levels is not None else ["state"],
        party_id=party_id,
    )
    point.payload["publish_date"] = publish_date
    return point


def test_two_pass_historic_recency_decay_equal_cosine() -> None:
    """Two historic candidates with EQUAL cosine but different publish_date: the more
    recent one (closer to term_start) ranks first after decay."""
    # Passed in the WRONG order (older first) to prove decay re-orders the bucket.
    older = _dated_point(0.70, "2015-06-14", party_id="older")
    recent = _dated_point(0.70, "2020-06-14", party_id="recent")
    mock_client = _make_two_pass_client([], [older, recent])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_limit=2,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert [p["party_id"] for p in buckets["historic"]] == ["recent", "older"], (
        "at equal cosine the more-recent historic item must rank first after decay"
    )


def test_two_pass_historic_decay_monotonic_similarity_dominates() -> None:
    """A much-higher-similarity OLDER item still beats a slightly-lower-similarity
    recent item — decay lowers but does not invert a large cosine gap."""
    old_strong = _dated_point(0.95, "2019-03-14", party_id="old_strong")
    recent_weak = _dated_point(0.70, "2021-01-14", party_id="recent_weak")
    mock_client = _make_two_pass_client([], [recent_weak, old_strong])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_limit=2,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert [p["party_id"] for p in buckets["historic"]] == [
        "old_strong",
        "recent_weak",
    ], (
        "a much-higher-similarity older item must still outrank a slightly-lower recent item"
    )


def test_two_pass_historic_enlarged_pool_then_truncated() -> None:
    """The historic pass over-fetches an enlarged pool (limit > historic_limit) and
    then truncates to historic_limit after the decay re-rank."""
    hist = [
        _dated_point(0.70, f"2020-0{i}-14", party_id=f"h{i}") for i in range(1, 6)
    ]  # 5 candidates
    mock_client = _make_two_pass_client([], hist)

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_limit=2,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    _cur_call, hist_call = mock_client.query_points.call_args_list
    assert hist_call.kwargs["limit"] > 2, (
        "historic pass must over-fetch an enlarged pool"
    )
    assert hist_call.kwargs["limit"] == 20, (
        "max(historic_limit * 10, 20) == 20 for limit=2"
    )
    assert len(buckets["historic"]) == 2, "bucket must be truncated to historic_limit"


def test_two_pass_historic_missing_or_unparseable_date_decay_one() -> None:
    """Missing / unparseable publish_date → decay 1.0 (no penalty), no crash. The
    full-score undated items therefore outrank a heavily-decayed old dated item."""
    missing = _make_point(0.66, "DE-BY", ["state"], party_id="missing")
    del missing.payload["publish_date"]
    garbage = _make_point(0.64, "DE-BY", ["state"], party_id="garbage")
    garbage.payload["publish_date"] = "not-a-date"
    old = _dated_point(0.62, "2012-06-14", party_id="old")  # heavily decayed
    mock_client = _make_two_pass_client([], [old, missing, garbage])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_limit=3,
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    parties = [p["party_id"] for p in buckets["historic"]]
    assert parties[0] == "missing", (
        "undated item keeps full score (decay 1.0) → ranks first"
    )
    assert parties[1] == "garbage", "unparseable date keeps full score (decay 1.0)"
    assert parties[-1] == "old", "heavily-decayed old dated item ranks last"


def test_two_pass_current_bucket_no_decay() -> None:
    """The current bucket is NOT recency-weighted: in-window points with different
    publish_dates keep their original Qdrant order (flat)."""
    older = _dated_point(
        0.70, "2021-06-14", party_id="older"
    )  # in-window, listed first
    recent = _dated_point(0.70, "2025-06-14", party_id="recent")  # in-window
    mock_client = _make_two_pass_client([older, recent], [])

    buckets = retrieve_two_pass(
        "Haushalt",
        term_start=_TERM_START,
        term_end=_TERM_END,
        source_type="vote_record",
        region_path=["DE", "DE-BY"],
        historic_score_threshold=0.60,
        query_vector=_ZERO_VECTOR,
        _client=mock_client,
    )

    assert [p["party_id"] for p in buckets["current"]] == ["older", "recent"], (
        "current bucket must stay flat (Qdrant order preserved, no recency decay)"
    )


# ---------------------------------------------------------------------------
# test_prefer_op_dedup — post-fetch prefer-op dedup on shared speech_key
#
# The dedup helper does not exist yet. This test
# Skips until retrieve exposes `dedup_prefer_op` (or equivalent),
# then asserts: dip+op sharing a speech_key collapse to the op member; a chunk
# with a missing speech_key is always kept; the bucket does not shrink below
# the number of distinct speeches.
# ---------------------------------------------------------------------------


def _speech_point(
    source: str,
    speech_key: str | None,
    party_id: str,
    source_item_id: str | None = None,
) -> dict:
    """A minimal parliamentary_speech payload dict as returned post-fetch.

    ``source_item_id`` is the per-source distinct-speech id (op originMediaID /
    DIP xml_rede_id). Chunks of ONE speech share it; distinct speeches differ.
    Defaults to a unique id derived from party_id so each ad-hoc point is its own
    distinct speech unless a caller pins the id (multi-chunk / collision tests).
    """
    payload = {
        "source_type": "parliamentary_speech",
        "source": source,
        "party_id": party_id,
        "source_item_id": source_item_id or f"{source}-{party_id}",
        "text": f"speech source={source} key={speech_key}",
    }
    if speech_key is not None:
        payload["speech_key"] = speech_key
    return payload


def test_prefer_op_dedup() -> None:
    """post-fetch dedup keeps the op member on a shared speech_key; missing key = keep."""
    from src.ingestion.retrieve import dedup_prefer_op as dedup

    shared = "de-20-101-mareike-lotte-wulf-top20"
    results = [
        _speech_point("dip", shared, party_id="dip_dup"),
        _speech_point("op", shared, party_id="op_winner"),
        _speech_point("dip", None, party_id="legacy_no_key"),  # missing key → keep
        _speech_point("op", "de-20-101-other-speaker-top21", party_id="op_solo"),
    ]

    deduped = dedup(results)

    sources_by_key = {
        p.get("speech_key"): p["source"] for p in deduped if p.get("speech_key")
    }
    assert sources_by_key.get(shared) == "op", (
        "shared speech_key must keep the op member"
    )

    # Missing-key legacy chunk is never dropped.
    assert any(p["party_id"] == "legacy_no_key" for p in deduped), (
        "a chunk with no speech_key must be treated as no-duplicate and kept"
    )
    # No bucket shrink below the count of distinct speeches (2 keyed + 1 keyless = 3).
    assert len(deduped) == 3


def test_prefer_op_dedup_grafts_transcript_pdf() -> None:
    """The prefer-op collapse salvages the dip duplicate's transcript PDF onto the
    surviving op record (query-time mirror of the ingest-time supersede graft), so a
    dual-format speech source works even for corpora ingested before the merge."""
    from src.ingestion.retrieve import dedup_prefer_op as dedup

    shared = "de-20-101-mareike-lotte-wulf-top20"
    pdf = "https://dserver.bundestag.de/btp/20/2000101.pdf"
    dip = _speech_point("dip", shared, party_id="dip_dup")
    dip["citation_url"] = pdf
    op = _speech_point("op", shared, party_id="op_winner")  # no transcript_pdf_url yet

    # Order A — dip first, op second (incoming op replaces the dip slot).
    survivor_a = next(
        p for p in dedup([dict(dip), dict(op)]) if p.get("speech_key") == shared
    )
    assert survivor_a["source"] == "op"
    assert (survivor_a.get("meta") or {}).get("transcript_pdf_url") == pdf

    # Order B — op first, dip second (existing op wins, dip still salvaged).
    survivor_b = next(
        p for p in dedup([dict(op), dict(dip)]) if p.get("speech_key") == shared
    )
    assert survivor_b["source"] == "op"
    assert (survivor_b.get("meta") or {}).get("transcript_pdf_url") == pdf

    # An op that ALREADY carries a transcript_pdf_url is not overwritten.
    op_with = _speech_point("op", shared, party_id="op_has")
    op_with["meta"] = {"transcript_pdf_url": "https://existing.example/keep.pdf"}
    dip_other = _speech_point("dip", shared, party_id="dip_other")
    dip_other["citation_url"] = pdf
    survivor_c = next(
        p
        for p in dedup([dict(op_with), dict(dip_other)])
        if p.get("speech_key") == shared
    )
    assert (
        survivor_c["meta"]["transcript_pdf_url"] == "https://existing.example/keep.pdf"
    )


def test_prefer_op_dedup_keeps_distinct_op_speeches_sharing_a_key() -> None:
    """Regression: ``speech_key`` is not unique per speech (multi-chunk speech,
    or a speaker speaking twice under the same agenda item). Two DISTINCT op members
    that share a key must BOTH survive — the old group-by-key collapse silently
    dropped ~7% of op speeches from retrieval."""
    import src.ingestion.retrieve as retrieve_mod

    dedup = retrieve_mod.dedup_prefer_op
    shared = "de-20-101-soeren-bartol-top2"
    a = _speech_point("op", shared, party_id="op_a")
    a["text"] = "first speech under this agenda item"
    b = _speech_point("op", shared, party_id="op_b")
    b["text"] = "second, distinct speech under the same agenda item"

    deduped = dedup([a, b])
    texts = {p["text"] for p in deduped if p.get("speech_key") == shared}
    assert len(deduped) == 2, "both distinct op speeches sharing a key must survive"
    assert texts == {a["text"], b["text"]}


def test_prefer_op_dedup_keeps_distinct_dip_speeches_without_op_twin() -> None:
    """Two distinct DIP speeches sharing a key (no op member) must both survive —
    only a DIP with a real cross-source op twin in the batch is dropped."""
    import src.ingestion.retrieve as retrieve_mod

    dedup = retrieve_mod.dedup_prefer_op
    shared = "de-20-101-soeren-bartol-top2"
    a = _speech_point("dip", shared, party_id="dip_a")
    a["text"] = "first dip speech"
    b = _speech_point("dip", shared, party_id="dip_b")
    b["text"] = "second, distinct dip speech"

    deduped = dedup([a, b])
    assert len(deduped) == 2, "distinct dip speeches with no op twin must both survive"


def test_prefer_op_dedup_multichunk_speech_collapses_by_source_item_id() -> None:
    """A long speech is several chunks sharing ONE source_item_id + speech_key.
    A 1-op-speech / 1-dip-speech group (each multi-chunk) is an unambiguous twin:
    keep BOTH op chunks, drop BOTH dip chunks (op carries the full text)."""
    import src.ingestion.retrieve as retrieve_mod

    dedup = retrieve_mod.dedup_prefer_op
    key = "de-20-101-hubertus-heil-top20"
    op0 = _speech_point("op", key, "op", source_item_id="op-heil")
    op1 = _speech_point(
        "op", key, "op", source_item_id="op-heil"
    )  # chunk 1, same speech
    dip0 = _speech_point("dip", key, "dip", source_item_id="dip-heil")
    dip1 = _speech_point("dip", key, "dip", source_item_id="dip-heil")

    deduped = dedup([op0, dip0, op1, dip1])
    assert [p["source"] for p in deduped] == ["op", "op"], (
        "both op chunks kept, both dip chunks (the single twin) dropped"
    )


def test_prefer_op_dedup_ambiguous_group_keeps_dip_op_does_not_have() -> None:
    """Core: two DISTINCT op speeches + one dip speech share a key. The dip
    might be a distinct speech op did NOT align, so it must NOT be dropped (would
    be a grounding loss). Ambiguous group (2 distinct op) → keep everything."""
    import src.ingestion.retrieve as retrieve_mod

    dedup = retrieve_mod.dedup_prefer_op
    key = "de-20-143-rita-schwarzeluehr-sutter-top3"
    op_a = _speech_point("op", key, "op_a", source_item_id="op-A")
    op_b = _speech_point("op", key, "op_b", source_item_id="op-B")
    dip_x = _speech_point("dip", key, "dip_x", source_item_id="dip-X")

    deduped = dedup([op_a, op_b, dip_x])
    assert len(deduped) == 3, "ambiguous group must keep all — no dip dropped"
    assert any(p["source"] == "dip" for p in deduped)
