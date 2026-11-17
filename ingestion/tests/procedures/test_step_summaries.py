# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import asyncio
from datetime import date
from typing import Any

from ingestion.procedures.step_summaries import (
    Document,
    SummaryCheck,
    WrittenSummary,
    summarise,
    summarise_procedures,
)
from tests.procedures.fakes import FakeQdrant
from wahlchat_common.procedures import ProcedureRecord, ProcedureStage, StepSummary

TODAY = date(2026, 11, 17)


class Model:
    """Writes the next draft; confirms only the drafts in ``good``."""

    def __init__(self, drafts: list[str], good: set[str]) -> None:
        self.drafts, self.good, self.prompts = list(drafts), good, []

    async def __call__(self, messages: list[Any], schema: type) -> tuple[Any, str]:
        prompt = messages[0].content
        self.prompts.append(prompt)
        if schema is WrittenSummary:
            return WrittenSummary(summary=self.drafts.pop(0)), "gemini-test"
        draft = prompt.split("Zusammenfassung:\n", 1)[1].split("\n", 1)[0]
        ok = draft in self.good
        return SummaryCheck(supported=ok, problems=[] if ok else ["Ziel als Tatsache"]), "gemini-test"


DOC = Document(number="21/9161", doc_type="Beschlussempfehlung und Bericht",
               title="Reform des Nachrichtendienstrechts", urheber=["Innenausschuss"], text="Vorblatt …")


def test_a_confirmed_summary_is_kept() -> None:
    model = Model(["Der Innenausschuss empfiehlt Änderungen."], {"Der Innenausschuss empfiehlt Änderungen."})
    assert asyncio.run(summarise(DOC, model)) == ("Der Innenausschuss empfiehlt Änderungen.", "gemini-test")


def test_a_rejected_draft_is_rewritten_with_the_objections() -> None:
    model = Model(["Das Gesetz schützt Deutschland.", "Die Bundesregierung will Deutschland schützen."],
                  {"Die Bundesregierung will Deutschland schützen."})
    assert asyncio.run(summarise(DOC, model))[0] == "Die Bundesregierung will Deutschland schützen."
    assert "Ziel als Tatsache" in model.prompts[2]


def test_twice_rejected_means_no_summary() -> None:
    assert asyncio.run(summarise(DOC, Model(["a", "b"], set()))) is None


def law(summaries: dict[str, StepSummary] | None = None) -> ProcedureRecord:
    return ProcedureRecord(
        vorgang_id="338341", wahlperiode=21, vorgangstyp="Gesetzgebung", kind="legislation",
        titel="Gesetz zur Reform des Nachrichtendienstrechts",
        stages=[
            ProcedureStage(position_id="1", date=date(2026, 9, 7), chamber="BT", name="Gesetzentwurf",
                           document_kind="Drucksache", document_number="21/7868"),
            ProcedureStage(position_id="2", date=date(2026, 9, 24), chamber="BT", name="1. Beratung",
                           document_kind="Plenarprotokoll", document_number="21/96"),
            ProcedureStage(position_id="3", date=date(2026, 11, 11), chamber="BT",
                           name="Beschlussempfehlung und Bericht", document_kind="Drucksache",
                           document_number="21/9161"),
        ],
        step_summaries=summaries or {},
        dip_url="https://dip.bundestag.de/vorgang/x/338341", dip_updated_at="", content_hash="",
    )


def qdrant_with(*numbers: str) -> FakeQdrant:
    qdrant = FakeQdrant()
    for n in numbers:
        qdrant.add(n, {"source_parent_key": f"drucksache:BT:{n}", "doc_section": "overview",
                       "chunk_index": 0, "text": f"Vorblatt {n}", "meta": {"doc_type": "Gesetzentwurf"}})
    return qdrant


def run(record: ProcedureRecord, qdrant: FakeQdrant, model: Model) -> tuple[Any, dict]:
    written: dict[str, dict[str, StepSummary]] = {}
    report = asyncio.run(summarise_procedures(
        {record.vorgang_id: record}, qdrant=qdrant, collection="c", call=model, today=TODAY,
        write=lambda vid, s: written.__setitem__(vid, s),
    ))
    return report, written


def test_draft_and_committee_report_are_summarised_once() -> None:
    report, written = run(law(), qdrant_with("21/7868", "21/9161"), Model(["A", "B"], {"A", "B"}))
    assert sorted(report.written) == ["21/7868", "21/9161"]
    assert {n: s.text for n, s in written["338341"].items()} == {"21/7868": "A", "21/9161": "B"}
    stored = written["338341"]
    report, written = run(law(stored), qdrant_with("21/7868", "21/9161"), Model([], set()))
    assert report.written == [] and written == {}


def test_a_changed_text_whose_new_summary_fails_drops_the_old_one() -> None:
    old = StepSummary(text="alt", document_number="21/7868", source_hash="before", model="m", written_on=TODAY)
    report, written = run(law({"21/7868": old}), qdrant_with("21/7868"), Model(["x", "y"], set()))
    assert report.rejected == ["21/7868"]
    assert written["338341"] == {}
