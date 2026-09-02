# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pledge registry: the JSONL file of pledges WE submit to the queue API.

The Cambridge queue API exposes no pledge registry — the pledge list is ours.
Each JSONL row carries the queue-API job inputs (claim, pledge_date,
pledge_author, optional bundesland/party/time_range) plus optional wahl.chat
display metadata (source title/URL/locator, policy area, summary).

When a full Cambridge pledge dump arrives, only the ``PledgeInput`` field
mapping (or a small pre-processing step) should need adjusting — the rest of
the pipeline consumes ``PledgeInput`` instances.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.ingestion.ids import compute_source_item_id
from src.ingestion.party_slugs import (
    CANONICAL_PARTY_SLUGS,
    PARTY_SLUG_QUARANTINE,
    STATE_PARTY_SLUGS,
    normalize_party_label,
)
from src.ingestion.schemas import SourceType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bundesland (full name, as the queue API expects) → ISO 3166-2 region code.
# Codes MUST match the context seeds' region_path elements (e.g. the
# landtagswahl-sachsen-anhalt-2026 context carries ["DE", "DE-ST"]) or the
# retrieval-time MatchAny(region ∈ region_path) filter never fires.
# region_path is ["DE", <code>]; a pledge without a Bundesland is federal (["DE"]).
# ---------------------------------------------------------------------------
BUNDESLAND_TO_REGION: dict[str, str] = {
    "baden-württemberg": "DE-BW",
    "bayern": "DE-BY",
    "berlin": "DE-BE",
    "brandenburg": "DE-BB",
    "bremen": "DE-HB",
    "hamburg": "DE-HH",
    "hessen": "DE-HE",
    "mecklenburg-vorpommern": "DE-MV",
    "niedersachsen": "DE-NI",
    "nordrhein-westfalen": "DE-NW",
    "rheinland-pfalz": "DE-RP",
    "saarland": "DE-SL",
    "sachsen": "DE-SN",
    "sachsen-anhalt": "DE-ST",
    "schleswig-holstein": "DE-SH",
    "thüringen": "DE-TH",
}


def party_slug(author: str) -> str:
    """Map a pledge author/party label to the canonical wahl.chat slug.

    Resolution reuses the framework's shared tables (``party_slugs.py``); state
    suffixes like "CDU Sachsen-Anhalt" are stripped before lookup. Unknown
    labels quarantine to ``unbekannt`` (framework convention) — the pledge is
    still ingested, but stays unreachable until the slug table learns the party
    (the Firestore record keeps the verbatim ``pledge_author``).
    """
    normalized = normalize_party_label(author)
    candidates = [normalized]
    # "cdu sachsen-anhalt" → try the label with a trailing Bundesland removed.
    for bundesland in BUNDESLAND_TO_REGION:
        if normalized.endswith(f" {bundesland}"):
            candidates.append(normalized[: -len(bundesland) - 1].strip())
            break
    for candidate in candidates:
        slug = CANONICAL_PARTY_SLUGS.get(candidate) or STATE_PARTY_SLUGS.get(candidate)
        if slug:
            return slug
    logger.warning(
        "Unknown pledge party %r — quarantining as %r", author, PARTY_SLUG_QUARANTINE
    )
    return PARTY_SLUG_QUARANTINE


class PledgeInput(BaseModel):
    """One registry row: queue-API job inputs + optional wahl.chat metadata."""

    model_config = ConfigDict(extra="ignore")

    # --- queue API inputs -------------------------------------------------
    claim: str
    pledge_date: str = Field(..., description="YYYY-MM-DD")
    pledge_author: str
    party: Optional[str] = Field(
        None, description="API party filter; defaults to pledge_author"
    )
    bundesland: Optional[str] = Field(
        None, description="Full state name, e.g. 'Sachsen-Anhalt'; None = federal"
    )
    time_range: str = Field(
        "since_pledge_date",
        description="week | month | since_pledge_date (API README recommends the latter)",
    )
    include_bundestag: bool = True

    # --- wahl.chat metadata (optional) ------------------------------------
    pledge_id: Optional[str] = None
    party_id: Optional[str] = Field(
        None,
        description=(
            "Explicit canonical wahl.chat party slug. Set this for coalition "
            "pledges ('CDU X, SPD X, FDP X') where auto-derivation from "
            "pledge_author is ambiguous — convention: the lead (first-named) "
            "party. Falls back to party_slug(pledge_author)."
        ),
    )
    normalized_summary: Optional[str] = None
    policy_area: Optional[str] = None
    pledge_source_title: Optional[str] = None
    pledge_source_url: Optional[str] = None
    pledge_source_locator: Optional[str] = None
    context_id: Optional[str] = None

    def resolved_party_id(self) -> str:
        """Canonical wahl.chat party slug: explicit override, else derived."""
        return self.party_id or party_slug(self.pledge_author)

    @property
    def region(self) -> str:
        """Scalar region code (Qdrant MatchAny target)."""
        if not self.bundesland:
            return "DE"
        code = BUNDESLAND_TO_REGION.get(self.bundesland.strip().lower())
        if code is None:
            logger.warning(
                "Unknown Bundesland %r — treating pledge as federal", self.bundesland
            )
            return "DE"
        return code

    @property
    def region_path(self) -> list[str]:
        """Broad-to-narrow region path stored on the Firestore record."""
        region = self.region
        return ["DE"] if region == "DE" else ["DE", region]

    def resolved_pledge_id(self) -> str:
        """Deterministic pledge id.

        MUST stay ``party_id:claim:region`` so re-ingesting a pledge upserts the
        same Firestore doc and Qdrant point instead of duplicating them.
        """
        if self.pledge_id:
            return self.pledge_id
        return str(
            compute_source_item_id(
                SourceType.PLEDGE_RECORD.value,
                f"{self.resolved_party_id()}:{self.claim}:{self.region}",
            )
        )

    def job_inputs(self) -> dict:
        """The exact payload for POST /jobs ``inputs``."""
        inputs: dict = {
            "claim": self.claim,
            "pledge_date": self.pledge_date,
            "pledge_author": self.pledge_author,
            "time_range": self.time_range,
            "include_bundestag": self.include_bundestag,
        }
        if self.bundesland:
            inputs["bundesland"] = self.bundesland
        party = self.party or self.pledge_author
        if party:
            inputs["party"] = party
        return inputs


def load_pledge_registry(path: Path | str) -> list[PledgeInput]:
    """Load pledge inputs from a JSONL file, skipping malformed lines with a warning."""
    registry_path = Path(path)
    if not registry_path.exists():
        raise FileNotFoundError(f"Pledge registry not found: {registry_path}")

    inputs: list[PledgeInput] = []
    with registry_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                inputs.append(PledgeInput(**json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "Skipping malformed registry line %s:%d — %s",
                    registry_path,
                    line_no,
                    exc,
                )
    return inputs
