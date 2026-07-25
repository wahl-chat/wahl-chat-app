# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Canonical party-slug knowledge shared across connectors.

``party_id`` is the corpus tenant key, so the same real party MUST resolve to
the same slug no matter which connector produced the chunk — otherwise
tenant-filtered retrieval returns a vote but not the matching manifesto (or vice
versa). Historically each connector kept its own label→slug map and a parity
test tried to keep them in sync by convention. This module is the single source
of truth for the slugs that must agree; connectors compose their own map on top
of these layers plus any source-specific labels.

Two alignment layers:

- ``CANONICAL_PARTY_SLUGS`` — the major parties that appear in every source
  (votes, speeches, manifestos) and must tenant-align everywhere.
- ``STATE_PARTY_SLUGS`` — state/regional parties shared by votes and manifestos
  (plenary speeches only ever carry Bundestag fractions, so the speech connector
  deliberately does NOT include these — an unexpected state party in a speech
  label quarantines rather than silently mis-tenants).

The **CDU/CSU rule** (do NOT "simplify"): a joint ``"cdu/csu"`` fraction label
maps to ``"cdu"`` (the Union fraction, not splittable from the source), while a
standalone ``"csu"`` label maps to ``"csu"`` (a distinct tenant). Collapsing CSU
into CDU would mis-tenant CSU speeches/manifestos and break cross-source
alignment.
"""

from __future__ import annotations

import re

PARTY_SLUG_QUARANTINE = "unbekannt"

# Major parties present across all sources — the tenant-alignment core.
CANONICAL_PARTY_SLUGS: dict[str, str] = {
    "spd": "spd",
    "cdu/csu": "cdu",
    "cdu": "cdu",
    "csu": "csu",
    "bündnis 90/die grünen": "gruene",
    "bündnis 90/die grüne": "gruene",
    "die grünen": "gruene",
    "grüne": "gruene",
    "fdp": "fdp",
    "afd": "afd",
    "die linke": "linke",
    "die linke.": "linke",
    "linke": "linke",
    "bsw": "bsw",
    "fraktionslos": "fraktionslos",
}

# State/regional parties shared by the votes and manifesto connectors. Slugs
# kept identical between the two so cross-source retrieval returns both a
# party's vote_record and its party_manifesto chunks under one tenant.
STATE_PARTY_SLUGS: dict[str, str] = {
    "freie wähler": "fw",
    "ssw": "ssw",  # Südschleswigscher Wählerverband
    "bvb/freie wähler": "bvb-fw",  # BVB / Freie Wähler (Brandenburg)
    "volt": "volt",
    "piraten": "piraten",
    "ödp": "oedp",  # Ökologisch-Demokratische Partei
    "die basis": "basis",  # dieBasis
    "diebasis": "basis",  # dieBasis alternate label
    "bürger in wut": "biw",  # Bürger in Wut (Bremen)
}

# Invisible / zero-width formatting characters that sources occasionally embed in
# party names. The 20th/21st Bundestag Greens arrive as "BÜNDNIS 90/­DIE GRÜNEN"
# with a SOFT HYPHEN (U+00AD) between "90/" and "DIE", so a naive lowercase+strip
# lookup misses the map key and the whole Green fraction quarantines. NFKC does
# NOT remove U+00AD, so it must be stripped explicitly.
_INVISIBLE_CHARS_RE = re.compile("[­​‌‍⁠﻿]")


def normalize_party_label(label: str) -> str:
    """Normalise a party/fraction label for slug lookup.

    Removes invisible/zero-width formatting characters (notably the U+00AD soft
    hyphen), collapses internal whitespace runs to single spaces, strips, and
    lowercases — producing a key comparable against the maps above.
    """
    clean = _INVISIBLE_CHARS_RE.sub("", label)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip().lower()
