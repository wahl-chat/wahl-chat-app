# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for openparliament_tv.mappers.corpus (idempotency).

The module-under-test does not exist yet. The top-level
`pytest.importorskip(...)` makes this whole file SKIP cleanly until the corpus
mapper lands, at which point the real assertions run.

Covers:
  - test_one_chunk_and_sentence_map: exactly ONE ChunkRecord per aligned speech;
    meta["sentence_map"] is a non-empty list of {text, ts_start(float), ts_end(float)}.
  - test_faction_map: Q1023134→cdu, Q4316268→fraktionslos, Q127785176→bsw, empty→unbekannt.
  - test_idempotent_ids: same speech twice → identical compute_chunk_id; a changed
    transcript changes content_hash.
"""

from __future__ import annotations

import pytest

# SKIP until the op corpus mapper exists.
corpus = pytest.importorskip(
    "src.ingestion.connectors.openparliament_tv.mappers.corpus",
    reason="op corpus mapper not yet implemented",
)


def _aligned_proceedings_items(session_json: dict) -> list[dict]:
    """Return the fixture's two aligned+proceedings speech items."""
    out = []
    for item in session_json["data"]:
        if not item["media"].get("aligned"):
            continue
        if not any(tc.get("type") == "proceedings" for tc in item.get("textContents", [])):
            continue
        out.append(item)
    return out


def _build(item: dict):
    """Call the mapper's speech→ChunkRecord builder, tolerant of the entry-point name."""
    build = getattr(corpus, "build_chunk_records", None) or getattr(
        corpus, "build_chunk_records_from_speech"
    )
    return build(item)


def test_one_chunk_and_sentence_map(session_json: dict) -> None:
    """ONE chunk per aligned speech + a timed sentence_map in meta."""
    item = _aligned_proceedings_items(session_json)[0]
    records = _build(item)
    assert len(records) == 1, "op ingests exactly ONE whole-speech chunk"

    meta = records[0].meta or {}
    sentence_map = meta.get("sentence_map")
    assert isinstance(sentence_map, list) and sentence_map, "meta.sentence_map must be non-empty"
    for s in sentence_map:
        assert set(s) >= {"text", "ts_start", "ts_end"}
        assert isinstance(s["ts_start"], float)
        assert isinstance(s["ts_end"], float)
    # First sentence starts at the per-speech-relative 1.000s (string→float cast).
    assert sentence_map[0]["ts_start"] == pytest.approx(1.0)


def test_faction_map(session_json: dict) -> None:
    """faction.wid → party slug, incl. the corrected BSW / Fraktionslos map.

    Empty faction.wid (ministers/president) must fall back to `unbekannt`
    (or an MdB match) — NEVER a real party.
    """
    slug_of = getattr(corpus, "op_party_slug", None) or getattr(corpus, "party_slug_for_faction")

    def _slug(wid: str) -> str:
        return slug_of({"faction": {"wid": wid}}, {})

    assert _slug("Q1023134") == "cdu"
    assert _slug("Q4316268") == "fraktionslos"  # CORRECTED (was labelled BSW in source list)
    assert _slug("Q127785176") == "bsw"          # CORRECTED (BSW group, WP21)
    assert _slug("") == "unbekannt", "empty faction must never map to a real party"


def test_content_hash_includes_party_slug(session_json: dict, monkeypatch) -> None:
    """a party correction (same faction_wid) must change content_hash.

    The empty-faction MdB fallback / CSU refinement can change the resolved
    party_slug WITHOUT changing faction.wid. Since the runner's re-write guard
    keys on content_hash, party_slug MUST be in the hash — otherwise a corrected
    party would keep the stale (mis-tenanted) indexed party_id. Monkeypatching
    op_party_slug changes ONLY the resolved slug; every other hashed input (text,
    sentence_map, video_uri, faction_wid) comes from the identical item.
    """
    item = _aligned_proceedings_items(session_json)[0]

    monkeypatch.setattr(corpus, "op_party_slug", lambda person, lookup: "cdu")
    rec_cdu = _build(item)[0]

    monkeypatch.setattr(corpus, "op_party_slug", lambda person, lookup: "csu")
    rec_csu = _build(item)[0]

    assert rec_cdu.party_id == "cdu" and rec_csu.party_id == "csu"
    assert rec_cdu.content_hash != rec_csu.content_hash, (
        "content_hash must change when the resolved party_slug changes"
    )


def test_citation_url_falls_back_when_video_uri_absent(session_json: dict) -> None:
    """a None videoFileURI must NOT produce a literal 'None#t=...' url.

    The alignment gate checks aligned/proceedings, not videoFileURI, so an aligned item
    can still carry videoFileURI=None. The citation_url must then fall back to the
    source page (or None) rather than the broken 'None#t=<ts>' string.
    """
    import copy

    item = copy.deepcopy(_aligned_proceedings_items(session_json)[0])
    item["media"]["videoFileURI"] = None
    source_page = item["media"].get("sourcePage")

    rec = _build(item)[0]

    assert rec.citation_url is None or not rec.citation_url.startswith("None"), (
        f"citation_url must not be a literal 'None#t=...' string; got {rec.citation_url!r}"
    )
    assert "#t=" not in (rec.citation_url or ""), "no deep-link fragment without a video uri"
    assert rec.citation_url == (source_page or None)


def test_idempotent_ids(session_json: dict) -> None:
    """Same speech twice → identical chunk id; a changed transcript → changed content_hash."""
    item = _aligned_proceedings_items(session_json)[0]

    rec_a = _build(item)[0]
    rec_b = _build(item)[0]

    from src.ingestion.ids import compute_chunk_id

    id_a = compute_chunk_id(rec_a.source_item_id, rec_a.chunk_index)
    id_b = compute_chunk_id(rec_b.source_item_id, rec_b.chunk_index)
    assert id_a == id_b, "re-running the same speech must yield the same point id"

    # Mutate the transcript text → content_hash must change (change-aware re-upsert).
    import copy

    mutated = copy.deepcopy(item)
    proceedings = next(tc for tc in mutated["textContents"] if tc["type"] == "proceedings")
    proceedings["textBody"][0]["text"] += " Zusätzlicher, korrigierter Satz."
    rec_c = _build(mutated)[0]
    assert rec_c.content_hash != rec_a.content_hash, (
        "a changed transcript must change content_hash so the runner re-writes the chunk"
    )
