# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Bundestag procedures (DIP Vorgänge) shared by the writer and the readers.

Firestore ``procedures/{vorgang_id}`` holds the full record: stages, decisions,
Drucksachen and topics. Qdrant holds one profile vector per procedure for
search, and every linked vote, speech and Drucksache chunk carries the
procedure's id in its indexed ``vorgang_ids``.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

PROCEDURES_COLLECTION = "procedures"

ProcedureKind = Literal[
    "legislation", "motion", "debate", "questions", "report", "procedural"
]

Chamber = Literal["BT", "BR", "BV", "EK"]

# overview: Vorblatt, Antrag text; report: a committee's Bericht (how it was
# deliberated, each Fraktion's stance). Law text and Begründung are not stored.
DocSection = Literal["overview", "report"]

LinkMethod = Literal[
    # votes
    "tally",
    "tally_drucksache",
    "drucksache_date",
    # speeches
    "name",
    "name_page",
    "name_order",
    "fuzzy_name",
    # chunks whose source names the procedure itself
    "source",
    # checked, nothing in scope
    "out_of_scope",
    "none",
]


class StageDecision(BaseModel):
    """What the chamber decided at a stage (DIP ``beschlussfassung``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenor: str = Field(..., description="e.g. 'Annahme in Ausschussfassung'")
    vote_kind: Optional[str] = Field(
        None, description="e.g. 'Namentliche Abstimmung'; None for a show of hands"
    )
    result: Optional[str] = Field(
        None, description="DIP's result note, e.g. '512:206:0' (yes:no:abstain)"
    )
    majority: Optional[str] = Field(None, description="e.g. 'Zweidrittelmehrheit'")
    document_numbers: list[str] = Field(default_factory=list)
    page: Optional[str] = None


class ProcedureStage(BaseModel):
    """One dated step of a procedure (DIP ``vorgangsposition``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str
    date: Date
    chamber: Chamber
    name: str = Field(
        ..., description="e.g. '1. Beratung', 'Beschlussempfehlung und Bericht'"
    )
    document_kind: Optional[Literal["Drucksache", "Plenarprotokoll"]] = None
    document_number: Optional[str] = Field(
        None, description="e.g. '21/7860' or '21/91'"
    )
    page: Optional[str] = Field(None, description="Plenarprotokoll page, e.g. '11363C'")
    url: Optional[str] = Field(
        None, description="PDF link, with a page anchor for protocols"
    )
    pdf_page: Optional[int] = Field(
        None,
        ge=1,
        description="1-based PDF page of a Plenarprotokoll step; a Drucksache "
        "step starts on page 1",
    )
    decisions: list[StageDecision] = Field(default_factory=list)


class DrucksacheRef(BaseModel):
    """A Drucksache of the procedure, without its text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: str = Field(..., description="BT '21/7860' or BR '442/26'")
    chamber: Chamber
    doc_type: Optional[str] = Field(None, description="e.g. 'Gesetzentwurf', 'Antrag'")
    date: Optional[Date] = None
    urheber: list[str] = Field(default_factory=list)
    party_ids: list[str] = Field(
        default_factory=list, description="Slugs of the Fraktionen among the urheber"
    )
    pdf_url: Optional[str] = None


class StepSummary(BaseModel):
    """A short summary of one stage's Drucksache, written once by a model and
    checked against the text before it is stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Optional[str] = Field(
        ..., description="None when no draft passed the check; kept so it is not retried"
    )
    document_number: str
    source_hash: str = Field(..., description="sha256 of the text it was written from")
    model: str
    written_on: Date


class ProcedureRecord(BaseModel):
    """The stored procedure: Firestore ``procedures/{vorgang_id}``."""

    model_config = ConfigDict(extra="forbid")

    vorgang_id: str
    wahlperiode: int
    vorgangstyp: str
    kind: ProcedureKind
    titel: str
    abstract: Optional[str] = None
    beratungsstand: Optional[str] = None
    initiative: list[str] = Field(default_factory=list)
    initiative_party_ids: list[str] = Field(default_factory=list)
    sachgebiete: list[str] = Field(default_factory=list)
    deskriptoren: list[str] = Field(default_factory=list)
    gesta: Optional[str] = None
    started_on: Optional[Date] = None
    stages: list[ProcedureStage] = Field(default_factory=list)
    drucksachen: list[DrucksacheRef] = Field(default_factory=list)
    drucksache_numbers: list[str] = Field(
        default_factory=list, description="BT numbers, for array-contains lookups"
    )
    latest_stage: Optional[str] = None
    latest_stage_on: Optional[Date] = None
    stage_changed_on: Optional[Date] = Field(
        None, description="When a new dated stage was last seen; edits don't count"
    )
    has_links: bool = Field(
        False, description="Any vote, speech or feed item in our data points here"
    )
    step_summaries: dict[str, StepSummary] = Field(
        default_factory=dict, description="By Drucksache number; kept across DIP syncs"
    )
    dip_url: str
    dip_updated_at: str = Field(..., description="DIP 'aktualisiert' of the Vorgang")
    content_hash: str

    def summary(self) -> "ProcedureSummary":
        return ProcedureSummary(
            vorgang_id=self.vorgang_id,
            titel=self.titel,
            vorgangstyp=self.vorgangstyp,
            kind=self.kind,
            beratungsstand=self.beratungsstand,
            initiative=self.initiative,
            latest_stage=self.latest_stage,
            latest_stage_on=self.latest_stage_on,
            stage_changed_on=self.stage_changed_on,
            milestones=milestones(self.stages, self.step_summaries),
            dip_url=self.dip_url,
        )


class Milestone(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    date: Date
    chamber: Chamber
    name: str
    document_kind: Optional[Literal["Drucksache", "Plenarprotokoll"]] = None
    document_number: Optional[str] = None
    url: Optional[str] = None
    decisions: list[StageDecision] = Field(default_factory=list)
    summary: Optional[str] = Field(None, description="StepSummary.text of its Drucksache")


class ProcedureSummary(BaseModel):
    """A procedure as feed items and search results carry it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vorgang_id: str
    titel: str
    vorgangstyp: str
    kind: ProcedureKind
    beratungsstand: Optional[str] = None
    # Who tabled it, e.g. "Bundesregierung", "Fraktion der SPD".
    initiative: list[str] = Field(default_factory=list)
    latest_stage: Optional[str] = None
    latest_stage_on: Optional[Date] = None
    stage_changed_on: Optional[Date] = None
    milestones: list[Milestone] = Field(default_factory=list)
    dip_url: str


# Steps a reader would name when tracing a decision; committee referral
# changes and similar bookkeeping stay in ``stages`` only.
_MILESTONE_PREFIXES = (
    "Gesetzentwurf",
    "Antrag",
    "Entschließungsantrag",
    "1. Beratung",
    "2. Beratung",
    "3. Beratung",
    "Beratung",
    "Beschlussempfehlung",
    "Durchgang",
    "1. Durchgang",
    "2. Durchgang",
    "Abschließende Beratung",
    "Aktuelle Stunde",
    "Vereinbarte Debatte",
    "Regierungserklärung",
    "Befragung",
    "Verkündung",
)


def milestones(
    stages: list[ProcedureStage], summaries: Optional[dict[str, StepSummary]] = None
) -> list[Milestone]:
    """The stages a timeline shows, oldest first, one per (date, chamber, name).
    DIP lists some stages twice (once per Plenarprotokoll page); their
    decisions are merged into the one shown."""
    summaries = summaries or {}
    by_key: dict[tuple[Date, str, str], Milestone] = {}
    for stage in sorted(stages, key=lambda s: (s.date, s.position_id)):
        if not stage.name.startswith(_MILESTONE_PREFIXES):
            continue
        key = (stage.date, stage.chamber, stage.name)
        shown = by_key.get(key)
        if shown is not None:
            if stage.decisions:
                by_key[key] = shown.model_copy(
                    update={"decisions": [*shown.decisions, *stage.decisions]}
                )
            continue
        summary = summaries.get(stage.document_number or "")
        by_key[key] = Milestone(
            date=stage.date,
            chamber=stage.chamber,
            name=stage.name,
            document_kind=stage.document_kind,
            document_number=stage.document_number,
            url=stage.url,
            decisions=list(stage.decisions),
            summary=summary.text if summary is not None else None,
        )
    return list(by_key.values())
