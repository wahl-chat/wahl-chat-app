# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from wahlchat_common.procedures import (
    ProcedureRecord,
    ProcedureStage,
    ProcedureSummary,
    StageDecision,
    StepSummary,
    milestones,
)


def stage(pid: str, day: str, name: str, **extra: object) -> ProcedureStage:
    return ProcedureStage(
        position_id=pid, date=date.fromisoformat(day), chamber="BT", name=name, **extra
    )


def test_milestones_merge_decisions_of_a_stage_listed_twice() -> None:
    vote = StageDecision(
        tenor="Ablehnung des Änderungsantrags",
        vote_kind="Namentliche Abstimmung",
        result="257:313:2",
    )
    shown = milestones(
        [
            stage(
                "1",
                "2026-11-13",
                "2. Beratung",
                document_kind="Plenarprotokoll",
                document_number="21/109",
            ),
            stage("2", "2026-11-13", "2. Beratung", decisions=[vote]),
            stage("3", "2026-11-13", "Änderung der Ausschussüberweisung"),
        ]
    )
    assert [(m.name, m.document_number, m.decisions) for m in shown] == [
        ("2. Beratung", "21/109", [vote])
    ]


def test_milestones_carry_the_summary_of_their_drucksache() -> None:
    summary = StepSummary(
        text="Der Innenausschuss empfiehlt Änderungen.",
        document_number="21/9161",
        source_hash="h",
        model="m",
        written_on=date(2026, 11, 17),
    )
    shown = milestones(
        [
            stage(
                "1",
                "2026-11-11",
                "Beschlussempfehlung und Bericht",
                document_kind="Drucksache",
                document_number="21/9161",
                url="https://dserver.bundestag.de/btd/21/091/2109161.pdf",
            )
        ],
        {"21/9161": summary},
    )
    assert shown[0].summary == summary.text
    assert shown[0].url == "https://dserver.bundestag.de/btd/21/091/2109161.pdf"


def _summary() -> dict:
    return {
        "vorgang_id": "338366",
        "titel": "Haushaltsbegleitgesetz 2027",
        "vorgangstyp": "Gesetzgebung",
        "kind": "legislation",
        "milestones": [
            {"date": "2026-09-08", "chamber": "BT", "name": "1. Beratung", "new": 1}
        ],
        "dip_url": "https://dip.bundestag.de/vorgang/338366",
    }


def test_a_reader_ignores_fields_a_newer_writer_added() -> None:
    summary = ProcedureSummary.model_validate({**_summary(), "stage_label": "x"})
    assert summary.milestones[0].name == "1. Beratung"
    record = ProcedureRecord.model_validate(
        {
            **_summary(),
            "wahlperiode": 21,
            "stages": [
                {
                    "position_id": "1",
                    "date": "2026-09-08",
                    "chamber": "BT",
                    "name": "1. Beratung",
                    "decisions": [{"tenor": "Überweisung", "added": True}],
                    "added": True,
                }
            ],
            "drucksachen": [{"number": "21/7860", "chamber": "BT", "added": True}],
            "dip_updated_at": "2026-11-16T10:00:00+01:00",
            "content_hash": "h",
            "added_later": {"any": "value"},
        }
    )
    assert record.stages[0].decisions[0].tenor == "Überweisung"
    assert "added_later" not in record.model_dump()
