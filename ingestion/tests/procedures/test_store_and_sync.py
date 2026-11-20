# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from datetime import date, datetime, timezone
from typing import Any

import pytest

from ingestion.ids import compute_source_item_id
from ingestion.procedures.store import ProcedureStore, replace_parents
from ingestion.procedures.sync import run_sync
from ingestion.schemas import AuthorityTier, ChunkRecord, SourceType
from ingestion.ids import make_chunk_key

from .fakes import FakeDip, FakeEmbed, FakeFirestore, FakeQdrant

TODAY = date(2026, 11, 17)
NOW = datetime(2026, 11, 17, 5, 15, tzinfo=timezone.utc)


def _chunk(parent: str, index: int, text: str = "t") -> ChunkRecord:
    siid = compute_source_item_id("drucksache", parent)
    return ChunkRecord(
        chunk_key=make_chunk_key(siid, index),
        source_item_id=siid,
        chunk_index=index,
        text=text,
        party_id="_all",
        region="DE",
        authority_tier=AuthorityTier.FACTUAL_RECORD,
        source_type=SourceType.DRUCKSACHE,
        publish_date=TODAY,
        source_parent_key=parent,
        content_hash=f"{parent}:{index}:{text}",
    )


def _ids(qdrant: FakeQdrant, parent: str) -> set[int]:
    return {
        p["chunk_index"]
        for p in qdrant.points.values()
        if p["source_parent_key"] == parent
    }


def test_a_shrinking_parent_loses_only_its_orphans_after_the_upsert() -> None:
    qdrant, embed = FakeQdrant(), FakeEmbed()
    replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0), _chunk("d:1", 1)]})
    report = replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0, "new")]})
    assert _ids(qdrant, "d:1") == {0}
    assert report.deleted == 1
    # the upsert of the new chunk happened before the delete
    assert qdrant.upserts[-1] and qdrant.deletes[-1]


def test_a_parent_emitting_nothing_is_emptied() -> None:
    qdrant, embed = FakeQdrant(), FakeEmbed()
    replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0)]})
    replace_parents(qdrant, "c", embed, {"d:1": []})
    assert _ids(qdrant, "d:1") == set()


def test_an_unchanged_parent_is_neither_embedded_nor_written() -> None:
    qdrant, embed = FakeQdrant(), FakeEmbed()
    replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0)]})
    calls = len(embed.calls)
    report = replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0)]})
    assert report.skipped == 1 and len(embed.calls) == calls


def test_a_failing_upsert_keeps_the_old_points() -> None:
    qdrant, embed = FakeQdrant(), FakeEmbed()
    replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0), _chunk("d:1", 1)]})
    qdrant.fail_upsert_for = {"d:1"}
    report = replace_parents(qdrant, "c", embed, {"d:1": [_chunk("d:1", 0, "new")]})
    assert report.failed_parents == ["d:1"]
    assert _ids(qdrant, "d:1") == {0, 1}


def test_a_failing_embedding_fails_its_parents_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ingestion.procedures.store._embed_texts",
        lambda embed, texts: embed.embed_documents(texts),
    )
    qdrant = FakeQdrant()
    report = replace_parents(
        qdrant, "c", FakeEmbed(fail=True), {"d:1": [_chunk("d:1", 0)]}
    )
    assert report.failed_parents == ["d:1"] and not qdrant.points


def _dip(vorgaenge: Any, positions: Any, **kw: Any) -> FakeDip:
    return FakeDip(
        vorgaenge,
        positions,
        plenary={21: {"338366": "Gesetzgebung", "341570": "Vereinbarte Debatte"}},
        core={21: {"338366", "341758"}},
        **kw,
    )


def _run(
    dip: FakeDip,
    db: FakeFirestore,
    qdrant: FakeQdrant,
    *,
    backfill: bool,
    today: date = TODAY,
):
    return run_sync(
        dip=dip,
        store=ProcedureStore(db),
        qdrant=qdrant,
        collection="c",
        embed=FakeEmbed(),
        wahlperioden=[21],
        backfill=backfill,
        today=today,
        now=NOW,
    )


def test_backfill_stores_records_and_profile_chunks(vorgaenge, positions) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    report = _run(_dip(vorgaenge, positions), db, qdrant, backfill=True)
    assert set(db.data["procedures"]) == {"338366", "341758", "341570"}
    assert report.written == 3 and not report.failed
    profiles = [p for p in qdrant.points.values() if p["source_type"] == "procedure"]
    assert len(profiles) == 3
    assert db.data["procedures_meta"]["sync"]["dip_updated_through"] == NOW.isoformat()


def test_a_second_run_with_no_changes_writes_nothing(vorgaenge, positions) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _run(_dip(vorgaenge, positions), db, qdrant, backfill=True)
    upserts = len(qdrant.upserts)
    dip = _dip(vorgaenge, positions, updated={21: {"338366", "341758"}})
    report = _run(dip, db, qdrant, backfill=False)
    assert report.unchanged == 2 and report.written == 0
    assert len(qdrant.upserts) == upserts
    # delta reads from the watermark minus the overlap
    assert dip.updated_since == ["2026-11-16T05:15:00+00:00"]


def test_delta_without_a_backfill_refuses(vorgaenge, positions) -> None:
    with pytest.raises(RuntimeError, match="backfill"):
        _run(_dip(vorgaenge, positions), FakeFirestore(), FakeQdrant(), backfill=False)


def test_a_failed_batch_keeps_the_watermark_and_is_retried(
    vorgaenge, positions
) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    _run(_dip(vorgaenge, positions), db, qdrant, backfill=True)
    before = db.data["procedures_meta"]["sync"]["dip_updated_through"]
    failing = _dip(vorgaenge, positions, updated={21: {"341758"}}, fail={"positions"})
    report = _run(failing, db, qdrant, backfill=False, today=date(2026, 11, 18))
    state = db.data["procedures_meta"]["sync"]
    assert report.failed == ["341758"]
    assert state["dip_updated_through"] == before
    assert state["failed_ids"] == ["341758"]
    # next run retries the failed id even though DIP lists nothing new
    healed = _run(
        _dip(vorgaenge, positions), db, qdrant, backfill=False, today=date(2026, 11, 19)
    )
    assert not healed.failed and healed.unchanged == 1
    assert db.data["procedures_meta"]["sync"]["failed_ids"] == []


def test_a_new_stage_is_reported(vorgaenge, positions) -> None:
    db, qdrant = FakeFirestore(), FakeQdrant()
    trimmed = {**positions, "338366": positions["338366"][:-1]}
    _run(_dip(vorgaenge, trimmed), db, qdrant, backfill=True)
    report = _run(
        _dip(vorgaenge, positions, updated={21: {"338366"}}),
        db,
        qdrant,
        backfill=False,
        today=date(2026, 11, 18),
    )
    assert report.new_stage == ["338366"]
    assert db.data["procedures"]["338366"]["stage_changed_on"] == "2026-11-18"
    # the later steps' work is kept with the record, for a run that stops early
    state = db.data["procedures_meta"]["sync"]
    assert state["pending_feed"] == ["338366"]
    assert "338366" in state["pending_drucksachen"]


def test_single_questions_are_never_stored(vorgaenge, positions) -> None:
    frage = {**vorgaenge["341758"], "id": "9", "vorgangstyp": "Mündliche Frage"}
    dip = FakeDip(
        {**vorgaenge, "9": frage},
        positions,
        plenary={21: {"9": "Mündliche Frage"}},
        core={21: set()},
    )
    db = FakeFirestore()
    _run(dip, db, FakeQdrant(), backfill=True)
    assert "9" not in db.data.get("procedures", {})
