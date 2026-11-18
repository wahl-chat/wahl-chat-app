# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""get_process: name resolution, steps as sources, the two evidence variants."""

from __future__ import annotations

from types import SimpleNamespace

import json
from pathlib import Path
from typing import Any, Optional

import pytest
from pydantic import ValidationError

from src.generic_chat import process
from src.generic_chat.schemas import (
    Anchor,
    AnchorContext,
    GetProcessInput,
    NumberedDocument,
    ProcedureRef,
    ToolResult,
)
from src.models.procedures import ProcedureView
from tests.generic_chat.conftest import make_deps
from wahlchat_common.procedures import ProcedureRecord

_FIXTURES = Path(__file__).parent.parent / "fixtures" / "procedures" / "records.json"
RECORDS = {r["vorgang_id"]: ProcedureRecord.model_validate(r) for r in json.loads(_FIXTURES.read_text())}
HBG = RECORDS["338366"]
GG = RECORDS["320784"]


def variant(record: ProcedureRecord, **update: Any) -> ProcedureRecord:
    return record.model_copy(update=update)


HG = variant(HBG, vorgang_id="338317", titel="Haushaltsgesetz 2027")
HBG_OLD = variant(HBG, vorgang_id="300001", wahlperiode=20, beratungsstand="Erledigt durch Ablauf der Wahlperiode")
GG_LATER = variant(
    GG, vorgang_id="321691", wahlperiode=21, beratungsstand="Überwiesen",
    titel="Gesetz zur Änderung des Grundgesetzes (Artikel 143i)", deskriptoren=["Grundgesetz", "Altschulden"],
)
HBG_RESOLUTION = variant(
    HBG, vorgang_id="300002", vorgangstyp="Entschließungsantrag BT", kind="motion",
    titel="Entschließungsantrag zum Haushaltsbegleitgesetz 2027",
)


class FakeService:
    def __init__(self, ranked: list[tuple[ProcedureRecord, float]]) -> None:
        self.ranked = ranked
        self.records = {r.vorgang_id: r for r, _ in ranked} | RECORDS
        self.document_queries: list[Optional[str]] = []

    async def aget_procedure(self, vid: str) -> Optional[ProcedureRecord]:
        return self.records.get(vid)

    async def aget_procedures(self, ids: Any) -> list[ProcedureRecord]:
        return [self.records[i] for i in ids if i in self.records]

    async def asearch_procedures(self, query: str, **_: Any) -> list[tuple[Any, float]]:
        return [(r.summary(), score) for r, score in self.ranked]

    async def aget_procedure_view(self, vid: str, **_: Any) -> Optional[ProcedureView]:
        speeches = [
            {"speech_key": f"s{i}", "party_id": party, "publish_date": "2026-09-08",
             "citation_title": f"Rede {i}", "text": "…", "source_type": "parliamentary_speech"}
            for i, party in enumerate(["spd", "spd", "cdu", "afd", "gruene"])
        ]
        return ProcedureView(procedure=self.records[vid], speeches=speeches)

    async def asearch_procedure_documents(self, query: str, **kwargs: Any) -> list[dict]:
        self.document_queries.append(query)
        return [
            {"chunk_key": "d:1", "source_type": "drucksache", "publish_date": "2026-11-16",
             "citation_title": "Drucksache 21/9241: Haushaltsbegleitgesetz 2027",
             "citation_url": "https://dserver.bundestag.de/btd/21/092/2109241.pdf",
             "text": "Der Ausschuss empfiehlt die Annahme in geänderter Fassung.",
             "meta": {"doc_type": "Beschlussempfehlung und Bericht", "urheber": ["Haushaltsausschuss"]}},
        ]


@pytest.fixture
def service(monkeypatch: pytest.MonkeyPatch):
    def install(ranked: list[tuple[ProcedureRecord, float]]) -> FakeService:
        fake = FakeService(ranked)
        for name in (
            "aget_procedure", "aget_procedures", "asearch_procedures",
            "aget_procedure_view", "asearch_procedure_documents",
        ):
            monkeypatch.setattr(process.procedure_service, name, getattr(fake, name))
        monkeypatch.setattr(process, "_current_wahlperiode", lambda: 21)
        return fake

    return install


@pytest.mark.parametrize(
    "name, ranked, expected",
    [
        # An old dead draft scoring first loses to the current one.
        ("Haushaltsbegleitgesetz", [(HBG_OLD, 0.71), (HBG, 0.70)], ["338366"]),
        # An Entschließungsantrag folds into its law.
        ("Haushaltsbegleitgesetz", [(HBG_RESOLUTION, 0.72), (HBG, 0.71)], ["338366"]),
        # Only one title has the name in it, whatever the scores.
        ("Haushaltsbegleitgesetz", [(HG, 0.75), (HBG, 0.70)], ["338366"]),
        # Two live laws of this term both fit the name: stay open.
        ("Haushalt 2027", [(HBG, 0.70), (HG, 0.70)], ["338366", "338317"]),
        # No title has the name; far below the best is not a candidate.
        ("Etat", [(HBG, 0.80), (HG, 0.60)], ["338366"]),
        # A topic only DIP's descriptors carry, and a year from an earlier term.
        ("Grundgesetzänderung zur Schuldenbremse 2025", [(GG_LATER, 0.77), (GG, 0.76)], ["320784"]),
    ],
)
def test_narrow(name: str, ranked: list, expected: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "_current_wahlperiode", lambda: 21)
    assert [r.vorgang_id for r in process.narrow(name, ranked)] == expected


def test_narrow_by_question_topic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "_current_wahlperiode", lambda: 21)
    ranked = [(GG_LATER, 0.77), (GG, 0.76)]
    assert len(process.narrow("Grundgesetzänderung 2025", ranked)) == 2
    question = "Welche Ausnahmen von der Schuldenbremse hat die Grundgesetzänderung 2025 eingeführt?"
    assert [r.vorgang_id for r in process.narrow("Grundgesetzänderung 2025", ranked, question)] == ["320784"]


def test_exact_title_wins_over_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "_current_wahlperiode", lambda: 21)
    picked = process.narrow("Haushaltsgesetz 2027 (WP 21)", [(HBG, 0.9), (HG, 0.7)])
    assert [r.vorgang_id for r in picked] == ["338317"]


async def test_ambiguous_name_gives_choices_and_no_evidence(service) -> None:
    service([(HBG, 0.70), (HG, 0.69)])
    deps = make_deps()
    result = await process.get_process(deps, GetProcessInput(name="Haushalt 2027"))
    assert result.procedure is None
    assert [c.label for c in result.choices] == [
        "Haushaltsbegleitgesetz 2027 (WP 21)", "Haushaltsgesetz 2027 (WP 21)",
    ]
    assert deps.sources.entries == []
    assert "which one the user means" in (result.note or "")


async def test_an_attached_item_picks_its_law_instead_of_asking(service) -> None:
    service([(HBG, 0.70), (HG, 0.69)])
    deps = make_deps()
    linked = NumberedDocument(id=1, source_type="vote", text="…",
                              procedures=[ProcedureRef(vorgang_id="338317", title="Haushaltsgesetz 2027")])
    deps.anchor = AnchorContext(label="vote", result=ToolResult(documents=[linked]))
    result = await process.get_process(deps, GetProcessInput(name="Haushalt 2027"))
    assert result.choices == [] and result.procedure is not None
    assert result.procedure.vorgang_id == "338317"


async def test_capped_returns_steps_votes_speeches_documents(service) -> None:
    fake = service([])
    deps = make_deps()
    result = await process.get_process(
        deps, GetProcessInput(vorgang_id="338366", question="Was hat der Ausschuss geändert?"),
        evidence="capped",
    )
    assert result.procedure is not None and result.procedure.title == "Haushaltsbegleitgesetz 2027"
    assert [s.date for s in result.steps] == sorted(s.date for s in result.steps)
    cited = [s for s in result.steps if s.id is not None]
    assert cited and all(deps.sources.entries[s.id]["source_type"] == "procedure_step" for s in cited)
    speeches = [d for d in result.documents if d.source_type == "parliamentary_speech"]
    # One per party on the reading day.
    assert len(speeches) == len({d.party for d in speeches}) == 4
    drucksachen = [d for d in result.documents if d.source_type == "drucksache"]
    assert drucksachen[0].party == "Haushaltsausschuss"
    assert fake.document_queries == ["Was hat der Ausschuss geändert?"]


async def test_timeline_has_steps_only(service) -> None:
    service([])
    result = await process.get_process(
        make_deps(), GetProcessInput(vorgang_id="338366"), evidence="timeline"
    )
    assert result.steps and result.documents == []
    assert "search" in (result.note or "")


def test_input_needs_id_or_name() -> None:
    with pytest.raises(ValidationError):
        GetProcessInput()
    with pytest.raises(ValidationError):
        GetProcessInput(vorgang_id="1", name="x y")


def test_anchor_takes_a_procedure() -> None:
    assert Anchor(vorgang_id="338366").vorgang_id == "338366"
    with pytest.raises(ValidationError):
        Anchor(vorgang_id="338366", poll_id=1)
    with pytest.raises(ValidationError):
        Anchor(vorgang_id="abc")


def test_choice_label_uses_the_short_name() -> None:
    long = variant(HG, titel="Gesetz über die Feststellung des Bundeshaushaltsplans für das Haushaltsjahr 2027 (Haushaltsgesetz 2027 - HG 2027)")
    assert process._choice_label(long) == "Haushaltsgesetz 2027 (WP 21)"
    assert process.narrow("Haushaltsgesetz 2027 (WP 21)", [(HBG, 0.9), (long, 0.7)]) == [long]


async def test_a_lone_resolution_stands_for_its_law(service) -> None:
    law_ = variant(HBG, vorgang_id="325558", titel="Gesetz zur Modernisierung des Wehrdienstes - Wehrdienst-Modernisierungsgesetz (WDModG)")
    resolution = variant(
        HBG, vorgang_id="328892", kind="motion", vorgangstyp="Entschließungsantrag BT",
        titel="Entschließungsantrag zum Gesetz zur Modernisierung des Wehrdienstes\n(Wehrdienst-Modernisierungsgesetz - WDModG)",
    )
    fake = service([(resolution, 0.8)])
    fake.records[law_.vorgang_id] = law_

    async def search(query: str, **kwargs: Any) -> list[tuple[Any, float]]:
        pool = [law_] if kwargs.get("kinds") == ("legislation",) else [resolution]
        return [(r.summary(), 0.8) for r in pool]

    process.procedure_service.asearch_procedures = search  # type: ignore[assignment]
    record, choices, _ = await process.resolve(GetProcessInput(name="Wehrdienst-Modernisierungsgesetz"))
    assert record is not None and record.vorgang_id == "325558" and choices == []


def test_every_fraktion_of_a_reading_is_heard() -> None:
    speeches = [
        {"speech_key": f"s{i}", "party_id": party, "publish_date": "2026-09-24"}
        for i, party in enumerate(["cdu", "cdu", "spd", "afd", "afd", "gruene", "linke"])
    ]
    picked = process._spread_speeches(speeches, None)
    assert [s["party_id"] for s in picked] == ["cdu", "spd", "afd", "gruene", "linke"]
    own = [s for s in speeches if s["party_id"] == "afd"] * 2
    assert len(process._spread_speeches(own, "afd")) == 2


def test_the_newest_readings_win_when_speeches_run_over() -> None:
    speeches = [
        {"speech_key": f"{day}-{party}", "party_id": party, "publish_date": day}
        for day in ["2026-03-01", "2026-06-01", "2026-09-01"]
        for party in ["cdu", "spd", "afd", "gruene", "linke"]
    ]
    days = [s["publish_date"] for s in process._spread_speeches(speeches, None)]
    assert days == ["2026-03-01"] * 2 + ["2026-06-01"] * 5 + ["2026-09-01"] * 5


def test_steps_keep_the_vote_of_a_reading_listed_twice() -> None:
    from datetime import date

    from wahlchat_common.procedures import ProcedureStage, StageDecision

    vote = StageDecision(tenor="Annahme in Ausschussfassung", vote_kind="Namentliche Abstimmung", result="308:190:71")
    record = variant(HBG, stages=[
        ProcedureStage(position_id="1", date=date(2026, 11, 13), chamber="BT", name="3. Beratung"),
        ProcedureStage(position_id="2", date=date(2026, 11, 13), chamber="BT", name="3. Beratung", decisions=[vote]),
    ])
    steps = process._steps(make_deps(), record)
    assert [s.decisions for s in steps] == [["Annahme in Ausschussfassung · Namentliche Abstimmung · 308:190:71"]]


def test_an_exact_title_shared_by_parallel_drafts_picks_the_live_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(process, "_current_wahlperiode", lambda: 21)
    dead_twin = variant(HBG, vorgang_id="338367", beratungsstand="Erledigt durch Ablauf der Wahlperiode")
    picked = process.narrow("Haushaltsbegleitgesetz 2027", [(dead_twin, 0.8), (HBG, 0.79)])
    assert [r.vorgang_id for r in picked] == ["338366"]


def test_a_drucksache_source_carries_its_party_and_passage() -> None:
    deps = make_deps()
    doc = process._register_document(deps, {
        "citation_title": "Drucksache 21/9163: Änderungsantrag",
        "citation_url": "https://dserver.bundestag.de/btd/21/091/2109163.pdf",
        "party_ids": ["gruene"],
        "text": "Drucksache 21/9163 › Antrag\n\nDer Bundestag   wolle beschließen,",
        "meta": {"doc_type": "Änderungsantrag", "urheber": ["Fraktion BÜNDNIS 90/DIE GRÜNEN"]},
    })
    entry = deps.sources.entries[doc.id]
    assert entry["page"] == 1  # no page found: the PDF opens at its start
    assert entry["party_id"] == "gruene"
    assert entry["snippet"] == "Der Bundestag wolle beschließen,"

    joint = process._register_document(deps, {"citation_title": "Drucksache 21/1", "party_ids": ["spd", "cdu"], "text": "x"})
    assert "party_id" not in deps.sources.entries[joint.id]


def test_a_drucksache_opens_at_its_page() -> None:
    deps = make_deps()
    doc = process._register_document(deps, {"citation_title": "Drucksache 21/2", "text": "x", "meta": {"page_start": 7}})
    assert deps.sources.entries[doc.id]["page"] == 7


def test_a_protocol_step_opens_at_its_pdf_page() -> None:
    from datetime import date

    from wahlchat_common.procedures import Milestone

    deps = make_deps()
    stage = Milestone(
        date=date(2026, 11, 13), chamber="BT", name="2. Beratung", document_kind="Plenarprotokoll",
        document_number="21/89", url="https://dserver.bundestag.de/btp/21/21089.pdf#P.13554", pdf_page=42,
    )
    number = process._register_step(deps, SimpleNamespace(titel="Gesetz"), stage)  # type: ignore[arg-type]
    entry = deps.sources.entries[number]
    assert (entry["url"], entry["page"]) == ("https://dserver.bundestag.de/btp/21/21089.pdf", 42)
