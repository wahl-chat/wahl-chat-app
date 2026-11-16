# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from ingestion.procedures.bulk import drucksache_numbers_to_read, run
from ingestion.procedures.mapper import build_record

from .conftest import load
from .fakes import FakeDip, FakeEmbed, FakeFirestore, FakeQdrant

TODAY = date(2026, 11, 17)


def _dip(vorgaenge, positions) -> FakeDip:
    return FakeDip(
        vorgaenge, positions,
        plenary={21: {"338366": "Gesetzgebung"}},
        core={21: {"338366", "341758"}},
        activities={"21/91": load("aktivitaet_21_91")},
        texts={"21/7860": load("drucksache_21_7860"), "21/9233": load("drucksache_21_9233")},
    )


def _speeches(qdrant: FakeQdrant) -> None:
    for i, s in enumerate(load("speeches_21_91")):
        qdrant.add(f"sp{i}", {
            "source_type": "parliamentary_speech", "source": s["source"], "source_item_id": s["key"],
            "wahlperiode": 21, "region": "DE", "publish_date": "2026-09-08",
            "speech_key": "de-21-91-x-top1",
            "meta": {"speaker_name": s["speaker_name"], "source_page": s["page"], "origin_media_id": s["order"]},
        })


def test_a_backfill_run_syncs_reads_links_and_flags(vorgaenge, positions, capsys) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _speeches(qdrant)
    db.collection("feed_items").document("d").set({"parliament": "bundestag", "debate": {"drucksachen": ["21/7860"]}})
    code = run(
        dip=_dip(vorgaenge, positions), db=db, qdrant=qdrant, collection="c", embed=FakeEmbed(),
        wahlperioden=[21], backfill=True, drucksachen="overview", link=True, sync=True, feed=True,
        today=TODAY,
    )
    out = capsys.readouterr().out
    assert code == 0, out
    procedures = db.data["procedures"]
    assert procedures["338366"]["has_links"] is True
    assert procedures["341758"]["has_links"] is False  # an Antrag nobody spoke on yet
    sections = {p["doc_section"] for p in qdrant.points.values() if p["source_type"] == "drucksache"}
    assert sections == {"overview"}
    speeches = [p for p in qdrant.points.values() if p["source_type"] == "parliamentary_speech"]
    assert all("procedure_link" in p for p in speeches)  # every speech checked
    # the fixture DIP knows two procedures; speeches on other Einzelpläne stay unlinked
    assert any(p.get("vorgang_ids") == ["338366"] for p in speeches)
    assert db.data["feed_items"]["d"]["procedure_ids"] == ["338366"]
    assert db.data["procedures_meta"]["sync"]["drucksachen_mode"] == "overview"
    assert "Procedure links" in out


def test_documents_to_read(vorgaenge, positions) -> None:
    procedures = {"338366": build_record(vorgaenge["338366"], positions["338366"], previous=None, today=TODAY)}
    all_numbers = drucksache_numbers_to_read(procedures, stored=set(), changed=set(), mode_changed=False)
    assert "21/7860" in all_numbers
    assert drucksache_numbers_to_read(procedures, stored=all_numbers, changed=set(), mode_changed=False) == set()
    assert drucksache_numbers_to_read(procedures, stored=all_numbers, changed={"338366"}, mode_changed=False) == all_numbers
    assert drucksache_numbers_to_read(procedures, stored=all_numbers, changed=set(), mode_changed=True) == all_numbers
