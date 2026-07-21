# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Connector-level constants for the openparliament_tv package.

Source: the keyless OpenParliamentTV-Data-DE GitHub bulk repository. The op
`/search/media` HTTP API is deliberately NOT used this phase — the
GitHub `processed/` session files are BOTH the backfill and the incremental
mechanism.

Security: RAW_BASE and TREES_URL are pinned module constants — the fetch host is
NEVER derived from a caller arg, a session-supplied URI, or any runtime input
(mirrors bundestag_speeches/constants.BASE_URL and abgeordnetenwatch/_AW_BASE).
The client fetches ONLY `RAW_BASE + validated-basename`; source-supplied media
URIs (videoFileURI/audioFileURI/sourcePage) are stored as strings, never fetched
during ingest (SSRF mitigation).
"""

from __future__ import annotations

# Pinned raw-content host for individual session JSON files. Never derive from input.
RAW_BASE = (
    "https://raw.githubusercontent.com/"
    "OpenParliamentTV/OpenParliamentTV-Data-DE/main/processed"
)

# GitHub Git-trees API to enumerate the repository's `processed/` directory (keyless).
# `recursive=1` returns the full tree in one response; we filter to session files.
TREES_URL = (
    "https://api.github.com/repos/"
    "OpenParliamentTV/OpenParliamentTV-Data-DE/git/trees/main?recursive=1"
)

# Match `processed/YYYYY-session.json` bulk files.
#   WP20 sessions: 200XX / 201XX      (e.g. 20101 → EP 20, session 101)
#   WP21 sessions: 210XX + specials   (e.g. 21005)
# The leading `2[01]` anchors the electoral-period digit (20/21) and rejects paths
# outside `processed/`, so only pinned-shape basenames ever reach fetch_session_json.
SESSION_FILE_RE = r"^processed/(2[01]\d{3})-session\.json$"

# Lookback floor (days) for the incremental discover() re-scan.
# op aligns speeches ~3–4 weeks after a session; 60 days comfortably exceeds that
# backlog lag so a session that only *just* aligned below the prior cursor is
# still re-picked instead of being stranded forever. Re-exported from the shared
# speech-dedup module so the op and DIP windows can never drift apart.
from src.ingestion.speech_dedup import LOOKBACK_DAYS  # noqa: E402, F401

# Finite cap on the trees listing to bound memory / parse work on a hostile or
# runaway response (DoS mitigation). The full DE repo is a few thousand
# session files across two legislatures — 100k entries is provably generous.
_MAX_TREE_ENTRIES = 100_000

# CORRECTED Wikidata faction id → canonical party slug map.
# The public op source list mislabels two entries; this is the corrected mapping:
#   Q4316268    → fraktionslos  (NOT "BSW", as the raw source list labelled it)
#   Q127785176  → bsw           (the actual BSW group, WP21)
# An EMPTY faction.wid (ministers / president) is intentionally absent — it must
# fall back to an MdB match or `unbekannt` in the mapper, NEVER a real party.
_OP_FACTION_SLUG_MAP: dict[str, str] = {
    "Q1023134": "cdu",
    "Q2207512": "spd",
    "Q1007353": "gruene",
    "Q1387991": "fdp",
    "Q1826856": "linke",
    "Q42575708": "afd",
    "Q4316268": "fraktionslos",
    "Q127785176": "bsw",
}
