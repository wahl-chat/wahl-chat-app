# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Connector-level constants for the bundestag_speeches package.

DIP_API_KEY is read from .env.

Security: BASE_URL is a pinned module constant — never derived
from a caller arg or runtime input (mirrors abgeordnetenwatch/_AW_BASE).
"""

from __future__ import annotations

# DIP API base URL — pinned; never derive the host from a method arg.
BASE_URL = "https://search.dip.bundestag.de/api/v1"

# Hard page cap for DipClient.pages() (mirrors the AW client's _MAX_PAGES).
# Rationale: a full 20th Bundestag legislature (~4 years) has ~130 plenary protocols,
# each yielding roughly one DIP API page. 500 pages is more than enough for any
# plenary-protocol listing while preventing an infinite loop on a stuck/malformed cursor.
_MAX_PAGES = 500

# MdB-Stammdaten XML path (relative to ai-backend/). ~15 MB, gitignored.
# The speech connectors fetch it on demand at run time (mdb.ensure_mdb_lookup);
# `make fetch-mdb-stammdaten` pre-fetches it for the host dev loop.
MDB_STAMMDATEN_FILE = "data/MDB_STAMMDATEN.XML"

# Bundestag OpenData ZIP holding MDB_STAMMDATEN.XML. Pinned module constant —
# never derived from a caller arg. If this 404s the blob was rotated: get the
# current link from https://www.bundestag.de/services/opendata ("Stammdaten
# aller Abgeordneten"). Single source of truth for both the runtime fetch and
# `make fetch-mdb-stammdaten`.
MDB_STAMMDATEN_URL = "https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip"

# Party alias normalisation map — maps raw XML / DIP strings to canonical party labels.
# Keys are uppercased + whitespace-collapsed before lookup (see utils.normalize_party).
PARTY_ALIASES: dict[str, str] = {
    "SPD": "SPD",
    "SOZIALDEMOKRATISCHE PARTEI DEUTSCHLANDS": "SPD",
    "FRAKTION DER SOZIALDEMOKRATISCHEN PARTEI DEUTSCHLANDS": "SPD",
    "FRAKTION DER SPD (GAST)": "SPD",
    "CDU": "CDU",
    "CSU": "CSU",
    "CDU/CSU": "CDU/CSU",
    "CSUS": "CDU/CSU",
    "FRAKTION DER CHRISTLICH DEMOKRATISCHEN UNION/CHRISTLICH - SOZIALEN UNION": "CDU/CSU",
    "FRAKTION DER CHRISTLICH DEMOKRATISCHEN UNION/CHRISTLICH-SOZIALEN UNION": "CDU/CSU",
    "FRAKTION DER CDU/CSU (GAST)": "CDU/CSU",
    "BÜNDNIS 90/DIE GRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
    "GRÜNE": "BÜNDNIS 90/DIE GRÜNEN",
    "DIE GRÜNEN/BÜNDNIS 90": "BÜNDNIS 90/DIE GRÜNEN",
    "FRAKTION BÜNDNIS 90/DIE GRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
    "FRAKTION DIE GRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
    "FRAKTION DIE GRÜNEN/BÜNDNIS 90": "BÜNDNIS 90/DIE GRÜNEN",
    "GRUPPE BÜNDNIS 90/DIE GRÜNEN": "BÜNDNIS 90/DIE GRÜNEN",
    "FDP": "FDP",
    "FRAKTION DER FREIEN DEMOKRATISCHEN PARTEI": "FDP",
    "FRAKTION DER FDP (GAST)": "FDP",
    "AFD": "AfD",
    "FRAKTION ALTERNATIVE FÜR DEUTSCHLAND": "AfD",
    "DIE LINKE": "DIE LINKE",
    "DIE LINKE.": "DIE LINKE",
    "FRAKTION DIE LINKE": "DIE LINKE",
    "FRAKTION DIE LINKE.": "DIE LINKE",
    "GRUPPE DIE LINKE": "DIE LINKE",
    "BSW": "BSW",
    "GRUPPE BSW - BÜNDNIS SAHRA WAGENKNECHT - VERNUNFT UND GERECHTIGKEIT": "BSW",
    "FRAKTIONSLOS": "fraktionslos",
    "FRAKTIONSLOSER": "fraktionslos",
    "FRAKTIONSLOSE": "fraktionslos",
    "PLOS": "fraktionslos",
}

# Set of canonical party labels (values of PARTY_ALIASES) — used by is_known_party().
VALID_PARTIES: set[str] = set(PARTY_ALIASES.values())
