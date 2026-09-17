# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""PledgeTracker domain models.

PledgeTracker is a University of Cambridge research project (EMNLP 2025 demo)
that builds evidence timelines for political pledges from parliamentary
sources. Firestore (``pledges/{pledge_id}``) is the source of truth for full
records including timelines; Qdrant holds one lightweight vector per pledge for
retrieval only (see ``src/ingestion/connectors/pledgetracker``).
"""

from typing import Optional

from pydantic import BaseModel, Field


class PledgeTimelineEvent(BaseModel):
    """One event returned by PledgeTracker for a pledge timeline."""

    date: str = Field(..., description="Event date as reported by PledgeTracker")
    publication_date: Optional[str] = Field(
        None,
        description="Publication date when it differs from the event date",
    )
    event: str = Field(..., description="Human-readable event description")
    event_short: Optional[str] = Field(
        None,
        description=(
            "LLM-generated short German headline (<= ~8 words) for compact "
            "display. None when generation failed or has not run — the UI then "
            "falls back to the full event text."
        ),
    )
    url: Optional[str] = Field(None, description="Evidence source URL")
    title: Optional[str] = Field(None, description="Source document title, if any")
    bundesland: Optional[str] = Field(None, description="Bundesland from source, if any")
    source: Optional[str] = Field(None, description="Source type/name, e.g. BT-Drucksache")
    party: Optional[str] = Field(None, description="Source-side party attribution")
    actor_type: Optional[str] = Field(None, description="Source-side actor type")
    is_relevant_for_tracking: Optional[bool] = Field(
        None,
        description=(
            "Whether Cambridge labelled the event useful for pledge tracking. "
            "This is not a fulfilment verdict."
        ),
    )
    raw_label: Optional[str] = Field(
        None,
        description="Original PledgeTracker label, e.g. Ja/Nein",
    )
    confidence: Optional[float] = Field(None, description="PledgeTracker confidence/logprob")


class PledgeRecord(BaseModel):
    """Firestore source-of-truth record for a tracked political pledge."""

    pledge_id: str
    party_id: str
    claim: str
    normalized_summary: str
    region_path: list[str]
    region: str
    context_id: Optional[str] = None
    policy_area: Optional[str] = None
    pledge_date: Optional[str] = None
    pledge_source_title: Optional[str] = None
    pledge_source_url: Optional[str] = None
    pledge_source_locator: Optional[str] = None
    timeline_events: list[PledgeTimelineEvent] = Field(default_factory=list)
    last_checked_at: Optional[str] = None
    tracker_status: Optional[str] = "unknown"
    tracker_status_label: Optional[str] = Field(
        None,
        description=(
            "Human-readable process status for display, e.g. 'Beendet' or "
            "'In Bearbeitung'. Populated only when the source explicitly provides "
            "it; kept separate from the machine tracker_status so nothing is shown "
            "unless real data exists. Not a fulfilment verdict."
        ),
    )
    tracker_step: Optional[str] = Field(
        None,
        description=(
            "Current step in the process for display, e.g. 'Bundestag' or "
            "'Bundesrat'. Populated only when the source provides it."
        ),
    )


class PledgeTrackerSuggestions(BaseModel):
    """Inline chat payload attached to one party_complete event."""

    party_id: str
    pledges: list[PledgeRecord]
