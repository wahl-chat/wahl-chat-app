# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date
from functools import partial

import pytest

from ingestion.procedures import bulk
from ingestion.procedures.bulk import _clear_as_read, run
from ingestion.procedures.drucksachen import ingest_drucksachen
from ingestion.procedures.link_apply import Linker
from ingestion.procedures.store import ProcedureStore

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


def test_a_run_that_stops_after_the_sync_is_followed_up_next_time(
    vorgaenge, positions, capsys, monkeypatch
) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    trimmed = {**positions, "338366": positions["338366"][:-1]}
    _run(_dip(vorgaenge, trimmed), db, qdrant)
    db.collection("feed_items").document("d").set(
        {
            "parliament": "bundestag",
            "debate": {"drucksachen": ["21/7860"]},
            "procedure_ids": ["338366"],
            "procedures": [],
        }
    )
    moved = _dip(vorgaenge, positions)
    moved.updated = {21: {"338366"}}

    def stops(self, wahlperioden) -> None:
        raise RuntimeError("Qdrant timed out")

    with monkeypatch.context() as patched:
        patched.setattr(Linker, "link_votes", stops)
        with pytest.raises(RuntimeError):
            _run(
                moved,
                db,
                qdrant,
                backfill=False,
                link=True,
                feed=True,
                today=date(2026, 11, 18),
            )
    state = db.data["procedures_meta"]["sync"]
    assert state["pending_feed"] == ["338366"]
    assert state["pending_drucksachen"] == []  # that step ran before the stop
    assert db.data["feed_items"]["d"]["procedures"] == []

    # DIP lists nothing new; the stored record is current. The feed item is
    # refreshed from the pending work alone, and the web cache cleared.
    cleared: list[bool] = []
    again = _dip(vorgaenge, positions)
    code = _run(
        again,
        db,
        qdrant,
        backfill=False,
        link=True,
        feed=True,
        today=date(2026, 11, 19),
        revalidate=lambda: cleared.append(True),
    )
    assert code == 0, capsys.readouterr().out
    item = db.data["feed_items"]["d"]
    assert [p["vorgang_id"] for p in item["procedures"]] == ["338366"]
    assert db.data["procedures_meta"]["sync"]["pending_feed"] == []
    assert cleared == [True]

    # nothing pending, nothing updated: the cache is left alone
    _run(
        again,
        db,
        qdrant,
        backfill=False,
        link=True,
        feed=True,
        today=date(2026, 11, 20),
        revalidate=lambda: cleared.append(True),
    )
    assert cleared == [True]


def test_a_procedure_is_cleared_once_its_last_document_is_written(
    vorgaenge, positions, capsys
) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _run(_dip(vorgaenge, positions), db, qdrant)
    # 338366 has 21/7860 and 21/9241, 341758 has 21/9233
    cleared: list[set[str]] = []
    on_batch = _clear_as_read(ProcedureStore(db).all(), cleared.append)
    on_batch(["21/7860"], set())
    assert cleared == []
    on_batch(["21/9233", "21/9241"], set())
    assert cleared == [{"338366", "341758"}]


def test_a_procedure_with_a_failed_document_stays_pending(
    vorgaenge, positions, capsys
) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _run(_dip(vorgaenge, positions), db, qdrant)
    cleared: list[set[str]] = []
    on_batch = _clear_as_read(ProcedureStore(db).all(), cleared.append)
    on_batch(["21/7860"], {"21/7860"})
    on_batch(["21/9233", "21/9241"], set())
    assert cleared == [{"341758"}]


class _Killed(BaseException):
    """The job's process ending mid-step, as on running out of memory."""


def test_a_run_killed_while_reading_keeps_what_it_read(
    vorgaenge, positions, capsys, monkeypatch
) -> None:
    dip, db, qdrant = _dip(vorgaenge, positions), FakeFirestore(), FakeQdrant()
    monkeypatch.setattr(
        bulk, "ingest_drucksachen", partial(ingest_drucksachen, batch_size=1)
    )
    read = dip.drucksache_texts

    def killed_at_the_last(numbers):
        if "21/9241" in numbers:
            raise _Killed
        return read(numbers)

    monkeypatch.setattr(dip, "drucksache_texts", killed_at_the_last)
    with pytest.raises(_Killed):
        _run(dip, db, qdrant)
    # 341758's only document was written before the end; 338366's was not
    assert db.data["procedures_meta"]["sync"]["pending_drucksachen"] == ["338366"]
