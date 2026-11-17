# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from wahlchat_common.procedures import ProcedureStage, StageDecision, StepSummary, milestones


def stage(pid: str, day: str, name: str, **extra: object) -> ProcedureStage:
    return ProcedureStage(position_id=pid, date=date.fromisoformat(day), chamber="BT", name=name, **extra)


def test_milestones_merge_decisions_of_a_stage_listed_twice() -> None:
    vote = StageDecision(tenor="Ablehnung des Änderungsantrags", vote_kind="Namentliche Abstimmung", result="257:313:2")
    shown = milestones([
        stage("1", "2026-11-13", "2. Beratung", document_kind="Plenarprotokoll", document_number="21/109"),
        stage("2", "2026-11-13", "2. Beratung", decisions=[vote]),
        stage("3", "2026-11-13", "Änderung der Ausschussüberweisung"),
    ])
    assert [(m.name, m.document_number, m.decisions) for m in shown] == [("2. Beratung", "21/109", [vote])]


def test_milestones_carry_the_summary_of_their_drucksache() -> None:
    summary = StepSummary(
        text="Der Innenausschuss empfiehlt Änderungen.", document_number="21/9161",
        source_hash="h", model="m", written_on=date(2026, 11, 17),
    )
    shown = milestones(
        [stage("1", "2026-11-11", "Beschlussempfehlung und Bericht", document_kind="Drucksache",
               document_number="21/9161", url="https://dserver.bundestag.de/btd/21/091/2109161.pdf")],
        {"21/9161": summary},
    )
    assert shown[0].summary == summary.text
    assert shown[0].url == "https://dserver.bundestag.de/btd/21/091/2109161.pdf"
