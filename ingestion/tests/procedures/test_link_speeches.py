# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

from collections import Counter

from ingestion.procedures.link_speeches import Speech, name_key, resolve_protocol

from .conftest import load


def _act(aid: str, name: str, page: int, vids: list[str], art: str = "Rede", typ: str = "Gesetzgebung"):
    return {
        "id": aid,
        "aktivitaetsart": art,
        "titel": f"{name}, MdB, SPD",
        "fundstelle": {"dokumentnummer": "21/1", "seite": f"{page}B", "anfangsseite": page, "endseite": page + 1},
        "vorgangsbezug": [{"id": v, "vorgangstyp": typ} for v in vids],
    }


def test_name_key_drops_titles_accents_and_roles() -> None:
    assert name_key("Dr. h. c. Thomas Silberhorn, MdB, CDU/CSU") == "thomas silberhorn"
    assert name_key("Beatrix von Storch") == "beatrix storch"
    assert name_key("Dr. Carl-Philipp Sassenrath") == "carl-philipp sassenrath"
    assert name_key("Cem Özdemir") == "cem ozdemir"


def test_a_speaker_with_one_procedure_links_by_name() -> None:
    acts = [_act("1", "Anna Muster", 100, ["10"]), _act("2", "Anna Muster", 105, ["10"])]
    result = resolve_protocol([Speech("s", "op", "Anna Muster")], acts)["s"]
    assert result.vorgang_ids == ["10"] and result.method == "name"


def test_dip_speeches_pick_their_activity_by_page() -> None:
    acts = [_act("1", "Anna Muster", 100, ["10"]), _act("2", "Anna Muster", 120, ["20"])]
    out = resolve_protocol([Speech("a", "dip", "Anna Muster", page=120)], acts)
    assert out["a"].vorgang_ids == ["20"] and out["a"].method == "name_page"


def test_video_speeches_pair_by_order_when_the_counts_agree() -> None:
    acts = [_act("1", "Anna Muster", 100, ["10"]), _act("2", "Anna Muster", 120, ["20"])]
    speeches = [Speech("late", "op", "Anna Muster", order=9), Speech("early", "op", "Anna Muster", order=3)]
    out = resolve_protocol(speeches, acts)
    assert out["early"].vorgang_ids == ["10"] and out["late"].vorgang_ids == ["20"]
    assert out["early"].method == "name_order"


def test_video_speeches_stay_unlinked_when_the_counts_differ() -> None:
    acts = [_act("1", "Anna Muster", 100, ["10"]), _act("2", "Anna Muster", 120, ["20"])]
    out = resolve_protocol([Speech("only", "op", "Anna Muster", order=1)], acts)
    assert out["only"].method == "none"


def test_a_misspelt_name_matches_fuzzily() -> None:
    acts = [_act("1", "Johann Wadephul", 100, ["10"])]
    out = resolve_protocol([Speech("s", "op", "Hans Wadephul")], acts)
    assert out["s"].vorgang_ids == ["10"] and out["s"].method == "fuzzy_name"


def test_fragestunde_questions_are_out_of_scope() -> None:
    acts = [_act("1", "Anna Muster", 100, ["77"], art="Frage", typ="Mündliche Frage")]
    out = resolve_protocol([Speech("s", "dip", "Anna Muster", page=100)], acts)
    assert out["s"].method == "out_of_scope" and out["s"].vorgang_ids == []


def test_dip_and_op_versions_of_a_speech_agree() -> None:
    acts = [_act("1", "Anna Muster", 100, ["10"])]
    out = resolve_protocol([Speech("d", "dip", "Anna Muster", page=100), Speech("o", "op", "Anna Muster", order=1)], acts)
    assert out["d"].vorgang_ids == out["o"].vorgang_ids == ["10"]


def test_a_real_budget_debate_links_almost_every_speech() -> None:
    """Protocol 21/91 (budget week, 1. Beratung of the Einzelpläne)."""
    speeches = [
        Speech(s["key"], s["source"], s["speaker_name"] or "",
               page=int(s["page"]) if s["page"] else None,
               order=int(s["order"]) if s["order"] else None)
        for s in load("speeches_21_91")
    ]
    out = resolve_protocol(speeches, load("aktivitaet_21_91"))
    methods = Counter(r.method for r in out.values())
    linked = sum(n for m, n in methods.items() if m not in ("none", "out_of_scope"))
    assert linked / len(speeches) >= 0.9, methods
