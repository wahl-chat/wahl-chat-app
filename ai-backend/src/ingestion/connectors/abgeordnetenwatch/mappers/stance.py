# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Pure stance-derivation and fraction-aggregation mappers for the AW connector.

All functions in this module are I/O-free (no network, no Firestore, no
filesystem) and deterministic — suitable for unit testing without mocks.

Security notes:
  Elevation of Privilege mitigation: aggregate_fraction_tallies guards
  against the degenerate `fraction: []` case (verified poll 4539 idx 107).
  An empty-list fraction cannot cause a crash or a tally injection.

  Information disclosure: this module reads only poll/vote/fraction
  JSON fields; no code path reads users/{uid} data.  The import surface is
  restricted to stdlib only.

  Tampering: derive_stance checks for an exact top-two tie before
  applying stance_map, preventing Python-version-dependent sort instability.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PARTY_SLUG_QUARANTINE = "unbekannt"

# The only vote tokens AW emits that contribute to a tally.  Any other token
# (a new enum value, null, or a missing "vote" key) is skipped with a warning
# rather than crashing the whole run.
_VALID_VOTE_TOKENS = ("yes", "no", "abstain", "no_show")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def aggregate_fraction_tallies(votes: list[dict]) -> dict[int, dict]:
    """Group per-mandate votes by fraction_id, summing yes/no/abstain/no_show.

    Degenerate-input guard:
    Votes where the ``fraction`` field is not a dict (e.g., an empty list ``[]``
    for mandate-holders with no fraction at that time) are silently skipped.
    They do not raise, and they do not contribute to any fraction's tally.

    Args:
        votes: List of per-mandate vote dicts from the AW ``votes`` endpoint.
               Each item must have ``fraction`` (dict or list/None) and
               ``vote`` (str: "yes" | "no" | "abstain" | "no_show").

    Robustness guards — a single malformed vote must not abort the whole poll
    (or crash the embedding worker at chunk time):
    - A fraction dict missing ``id`` is skipped with a warning.
    - A vote whose ``vote`` token is not one of the four valid tokens (a new
      enum value, ``null``, or a missing key) is skipped with a warning instead
      of raising ``KeyError``/``TypeError``.

    Label determinism:
    The ``fraction`` dict stored on a tally is selected deterministically — the
    candidate with the lexicographically smallest ``label`` wins, so the chosen
    label does not depend on payload order even when AW emits inconsistent
    ``label`` strings across mandates of the same fraction_id (renamed Gruppen).

    Returns:
        Mapping from fraction_id (int) to a tally dict with keys
        ``yes``, ``no``, ``abstain``, ``no_show`` (int counts) and
        ``fraction`` (the deterministically selected fraction dict).
    """
    tallies: dict[int, dict] = {}
    for v in votes:
        frac = v.get("fraction")
        if not isinstance(frac, dict):
            # Degenerate case: fraction=[] or None — skip without raising
            continue
        fid = frac.get("id")
        if fid is None:
            logger.warning(
                "aggregate_fraction_tallies: fraction dict missing 'id' — "
                "skipping vote (fraction=%r)",
                frac,
            )
            continue

        vote = v.get("vote")
        if vote not in _VALID_VOTE_TOKENS:
            logger.warning(
                "aggregate_fraction_tallies: unexpected vote token %r for "
                "fraction_id=%s — skipping vote (valid tokens: %s)",
                vote,
                fid,
                _VALID_VOTE_TOKENS,
            )
            continue

        if fid not in tallies:
            tallies[fid] = {
                "yes": 0,
                "no": 0,
                "abstain": 0,
                "no_show": 0,
                "fraction": frac,
            }
        else:
            # Deterministic label selection — keep the candidate fraction
            # dict with the lexicographically smallest label so the chosen label
            # is stable regardless of payload order.
            stored_label = str(tallies[fid]["fraction"].get("label") or "")
            new_label = str(frac.get("label") or "")
            if new_label < stored_label:
                tallies[fid]["fraction"] = frac

        tallies[fid][vote] += 1
    return tallies


def derive_stance(yes: int, no: int, abstain: int, no_show: int) -> str:
    """Derive the fraction's stance from its tally (locked rule).

    Rule:
    1. Find the bucket with the largest count.
    2. If the top two buckets are tied, return ``"neutral"`` (tie-break guard —
       prevents Python sort instability from making this non-deterministic).
    3. Otherwise map the winning bucket:
       yes -> "agree", no -> "disagree", abstain -> "neutral", no_show -> "absent".

    Args:
        yes: Count of "yes" votes in the fraction.
        no: Count of "no" votes.
        abstain: Count of "abstain" votes.
        no_show: Count of "no_show" votes.

    Returns:
        One of: "agree", "disagree", "neutral", "absent".
    """
    buckets = [
        ("yes", yes),
        ("no", no),
        ("abstain", abstain),
        ("no_show", no_show),
    ]
    buckets.sort(key=lambda x: x[1], reverse=True)

    # Explicit tie check — do NOT rely on sort stability for tie resolution
    if buckets[0][1] == buckets[1][1]:
        return "neutral"

    # Intentional collapse (do NOT "fix"):
    # Per the locked stance rule, BOTH an exact top-two tie AND an
    # abstain-largest plurality deliberately map to "neutral". These two
    # semantically distinct cases ("no clear majority" vs. "deliberately
    # abstained") collapse to the same output by design — the deferred scoring
    # engine does not (yet) need to distinguish them. This is not a bug.
    stance_map = {
        "yes": "agree",
        "no": "disagree",
        "abstain": "neutral",
        "no_show": "absent",
    }
    return stance_map[buckets[0][0]]


def fraction_to_party_slug(fraction_id: int, fraction_map: dict[int, str]) -> str:
    """Resolve a fraction_id to a canonical party slug.

    Uses a runtime map built from the AW ``/fractions`` endpoint response.
    Unknown/unmapped fraction_ids (e.g., new Gruppen not yet in the map)
    route to the quarantine slug ``"unbekannt"``.

    Args:
        fraction_id: AW numeric fraction ID.
        fraction_map: Mapping of fraction_id -> canonical party slug.

    Returns:
        The party slug, or ``"unbekannt"`` if the fraction_id is not in the map.
    """
    return fraction_map.get(fraction_id, _PARTY_SLUG_QUARANTINE)


