# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date

from ingestion.procedures.bulk import known_empty, run
from ingestion.procedures.drucksachen import CHUNK_RULES

from .conftest import load
from .fakes import FakeDip, FakeEmbed, FakeFirestore, FakeQdrant

TODAY = date(2026, 11, 17)


def _dip(vorgaenge, positions) -> FakeDip:
    return FakeDip(
        vorgaenge,
        positions,
        plenary={21: {"338366": "Gesetzgebung"}},
        core={21: {"338366", "341758"}},
        activities={"21/91": load("aktivitaet_21_91")},
        texts={
            "21/7860": load("drucksache_21_7860"),
            "21/9233": load("drucksache_21_9233"),
        },
    )


def _speeches(qdrant: FakeQdrant) -> None:
    for i, s in enumerate(load("speeches_21_91")):
        qdrant.add(
            f"sp{i}",
            {
                "source_type": "parliamentary_speech",
                "source": s["source"],
                "source_item_id": s["key"],
                "wahlperiode": 21,
                "region": "DE",
                "publish_date": "2026-09-08",
                "speech_key": "de-21-91-x-top1",
                "meta": {
                    "speaker_name": s["speaker_name"],
                    "source_page": s["page"],
                    "origin_media_id": s["order"],
                },
            },
        )


def test_a_backfill_run_syncs_reads_links_and_flags(
    vorgaenge, positions, capsys
) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _speeches(qdrant)
    db.collection("feed_items").document("d").set(
        {"parliament": "bundestag", "debate": {"drucksachen": ["21/7860"]}}
    )
    code = run(
        dip=_dip(vorgaenge, positions),
        db=db,
        qdrant=qdrant,
        collection="c",
        embed=FakeEmbed(),
        wahlperioden=[21],
        backfill=True,
        link=True,
        sync=True,
        feed=True,
        today=TODAY,
    )
    out = capsys.readouterr().out
    assert code == 0, out
    procedures = db.data["procedures"]
    assert procedures["338366"]["has_links"] is True
    assert procedures["341758"]["has_links"] is False  # an Antrag nobody spoke on yet
    sections = {
        p["doc_section"]
        for p in qdrant.points.values()
        if p["source_type"] == "drucksache"
    }
    assert sections == {"overview"}
    speeches = [
        p for p in qdrant.points.values() if p["source_type"] == "parliamentary_speech"
    ]
    assert all("procedure_link" in p for p in speeches)  # every speech checked
    # the fixture DIP knows two procedures; speeches on other Einzelpläne stay unlinked
    assert any(p.get("vorgang_ids") == ["338366"] for p in speeches)
    assert db.data["feed_items"]["d"]["procedure_ids"] == ["338366"]
    assert "Procedure links" in out


def _run(dip, db, qdrant, **kw):
    args = dict(
        dip=dip,
        db=db,
        qdrant=qdrant,
        collection="c",
        embed=FakeEmbed(),
        wahlperioden=[21],
        backfill=True,
        link=False,
        sync=True,
        feed=False,
        today=TODAY,
    )
    return run(**{**args, **kw})


def test_documents_are_read_once(vorgaenge, positions, capsys) -> None:
    dip, db, qdrant = _dip(vorgaenge, positions), FakeFirestore(), FakeQdrant()
    _run(dip, db, qdrant)
    assert {"21/7860", "21/9233"} <= set(dip.text_reads)
    dip.text_reads.clear()
    _run(dip, db, qdrant, backfill=False)
    # unchanged procedures: stored documents are not asked for again
    assert "21/7860" not in dip.text_reads and "21/9233" not in dip.text_reads


def test_a_failed_document_fails_the_run(vorgaenge, positions, capsys) -> None:
    dip, db, qdrant = _dip(vorgaenge, positions), FakeFirestore(), FakeQdrant()
    dip.fail.add("texts")
    assert _run(dip, db, qdrant) == 1


def test_rebuilt_collection_gets_profiles_back_on_backfill(
    vorgaenge, positions, capsys
) -> None:
    dip, db, qdrant = _dip(vorgaenge, positions), FakeFirestore(), FakeQdrant()
    _run(dip, db, qdrant)
    qdrant.points.clear()
    _run(dip, db, qdrant)
    assert (
        sum(1 for p in qdrant.points.values() if p["source_type"] == "procedure") == 2
    )


def test_documents_without_chunks_are_read_again_under_new_rules() -> None:
    listed = {"drucksachen_without_chunks": ["21/7868"]}
    assert known_empty({**listed, "drucksachen_chunk_rules": CHUNK_RULES}) == {"21/7868"}
    assert known_empty({**listed, "drucksachen_chunk_rules": CHUNK_RULES - 1}) == set()
    assert known_empty(listed) == set()
