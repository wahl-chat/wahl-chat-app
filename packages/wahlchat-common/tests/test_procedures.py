# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from wahlchat_common.procedures import ProcedureRecord, ProcedureSummary


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
