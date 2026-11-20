# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import pytest

from ingestion.procedures.scope import in_scope, kind_of


@pytest.mark.parametrize("vorgangstyp", ["Gesetzgebung", "Antrag", "Aktuelle Stunde"])
def test_core_types_are_procedures_without_a_plenary_stage(vorgangstyp: str) -> None:
    assert in_scope(vorgangstyp, has_bt_plenary_stage=False)


def test_other_types_count_once_they_reach_the_plenary() -> None:
    assert in_scope("Große Anfrage", has_bt_plenary_stage=True)
    assert not in_scope("Große Anfrage", has_bt_plenary_stage=False)


@pytest.mark.parametrize("vorgangstyp", ["Mündliche Frage", "Schriftliche Frage"])
def test_single_questions_never_are(vorgangstyp: str) -> None:
    assert not in_scope(vorgangstyp, has_bt_plenary_stage=True)


def test_kinds() -> None:
    assert kind_of("Gesetzgebung") == "legislation"
    assert kind_of("Entschließungsantrag BT") == "motion"
    assert kind_of("Vereinbarte Debatte") == "debate"
    assert kind_of("Befragung der Bundesregierung") == "questions"
    assert kind_of("Wahl im BT") == "procedural"
