# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for additions to chatbot_async:
  - build_vote_documents: federal parliament label
  - generate_streaming_chatbot_response: conditional federal-origin disclosure
    note appended to answer_guidelines

These tests cover purely structural / label-generation behaviour — no LLM, no
network, no Qdrant connections required.
"""

import asyncio
import inspect

from src.chatbot_async import (
    build_vote_documents,
    generate_streaming_chatbot_response,
)
from src.models.context import ContextParty
from src.models.general import LLMSize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vote_payload(region: str, party_id: str = "spd") -> dict:
    """Build a minimal vote_record payload with the given region."""
    return {
        "citation_title": "Testabstimmung",
        "citation_url": "https://example.com/vote/1",
        "publish_date": "2024-01-15",
        "region": region,
        "meta": {
            "vote_results": [
                {
                    "party_id": party_id,
                    "stance": "yes",
                    "yes": 100,
                    "no": 0,
                    "abstain": 0,
                    "no_show": 0,
                }
            ],
            "motion_outcome": "accepted",
        },
    }


# ---------------------------------------------------------------------------
# Parlament line in build_vote_documents page_content
# ---------------------------------------------------------------------------


def test_build_vote_documents_federal_label() -> None:
    """region=='DE' -> 'Parlament: Bundestag (Bundesebene)'; state region -> 'Parlament: Landtag'."""
    federal_payload = _make_vote_payload("DE")
    state_payload = _make_vote_payload("DE-BY")

    federal_docs = build_vote_documents("spd", "SPD", [federal_payload])
    state_docs = build_vote_documents("spd", "SPD", [state_payload])

    assert len(federal_docs) == 1, "Expected 1 doc for federal vote"
    assert len(state_docs) == 1, "Expected 1 doc for state vote"

    federal_content = federal_docs[0].page_content
    state_content = state_docs[0].page_content

    assert "Parlament: Bundestag (Bundesebene)" in federal_content, (
        f"federal vote must include 'Parlament: Bundestag (Bundesebene)'. "
        f"Got: {federal_content!r}"
    )
    assert "Parlament: Landtag" in state_content, (
        f"state vote must include 'Parlament: Landtag'. Got: {state_content!r}"
    )
    # Bundesebene must NOT appear in state vote
    assert "Bundesebene" not in state_content, (
        "State vote page_content must not contain 'Bundesebene'"
    )


# ---------------------------------------------------------------------------
# election_level param + federal-origin disclosure note
# ---------------------------------------------------------------------------


def test_answer_guidelines_federal_note_state() -> None:
    """generate_streaming_chatbot_response accepts election_level parameter with default None."""
    sig = inspect.signature(generate_streaming_chatbot_response)
    assert "election_level" in sig.parameters, (
        "generate_streaming_chatbot_response must accept 'election_level' parameter"
    )
    param = sig.parameters["election_level"]
    # Default must be None (backward-compat for callers that do not set it)
    assert param.default is None, (
        f"election_level default must be None, got {param.default!r}"
    )


def test_federal_origin_disclosure_note_only_for_non_federal() -> None:
    """The disclosure note is emitted only for non-federal elections.

    Behavioural test of the shared helper used by BOTH the single-party and comparison
    paths: empty for federal/None, and a Bundestag-vs-Landtag note for state/municipal.
    """
    from src.chatbot_async import _federal_origin_disclosure_note

    assert _federal_origin_disclosure_note(None) == "", "None (unset) must emit no note"
    assert _federal_origin_disclosure_note("federal") == "", (
        "Federal election must emit no note"
    )

    for lvl in ("state", "municipal"):
        note = _federal_origin_disclosure_note(lvl)
        assert "Bundestag" in note, (
            f"{lvl}: note must reference Bundestag, got {note!r}"
        )
        assert "Landtag" in note, f"{lvl}: note must reference Landtag, got {note!r}"


def test_both_response_paths_apply_federal_disclosure(monkeypatch) -> None:
    """Both the single-party and comparison generators inject the non-federal
    Bundestag-vs-Landtag disclosure into the assembled system prompt, so it cannot be
    present in one path and missing in the other (the comparison path previously
    omitted it). Driven behaviourally by capturing each system prompt."""
    from src import chatbot_async as ca

    assert (
        "election_level"
        in inspect.signature(
            ca.generate_streaming_chatbot_comparing_response
        ).parameters
    ), "comparison generator must accept election_level"

    captured_single = _capture_system_prompt(monkeypatch)
    _run_single_party(election_level="state")
    assert "Bundestag" in captured_single["system"], (
        "single-party path must apply the disclosure for a non-federal election"
    )

    captured_comparison = _capture_system_prompt(monkeypatch)
    _run_comparison(election_level="state")
    assert "Bundestag" in captured_comparison["system"], (
        "comparison path must apply the disclosure for a non-federal election"
    )


# ---------------------------------------------------------------------------
# _source_structure_note (four-section soft lead-ins,
# historic marking, coverage transparency)
# ---------------------------------------------------------------------------


def test_source_structure_note_four_leadins() -> None:
    """The note always carries the four soft lead-in cues (illustrative, party
    name interpolated) and explicitly forbids rigid form headers."""
    from src.chatbot_async import _source_structure_note

    note = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=True,
        votes_present=True,
        speeches_present=True,
    )
    assert "Im Wahlprogramm fordert" in note, "missing Position (manifesto) lead-in"
    assert "Bei namentlichen Abstimmungen stimmte" in note, "missing Votes lead-in"
    assert "In Reden betonte" in note, "missing Speeches (Konjunktiv) lead-in"
    assert "Historisch (aus früheren Jahren)" in note, "missing Historic cue"
    assert "SPD" in note, "party name must be interpolated into the cues"
    # soft cues, NOT rigid form headers.
    assert "KEINE starren Formular-Überschriften" in note, (
        "note must forbid rigid form-like headers"
    )


def test_source_structure_note_historic_conditional() -> None:
    """The strong 'render a marked historic section, placed last' instruction
    fires only when has_historic is True; never invents a historic section."""
    from src.chatbot_async import _source_structure_note

    with_hist = _source_structure_note(
        "SPD",
        has_historic=True,
        manifesto_present=True,
        votes_present=True,
        speeches_present=True,
    )
    without_hist = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=True,
        votes_present=True,
        speeches_present=True,
    )
    assert "immer als letzter Abschnitt" in with_hist, (
        "has_historic=True must add the historic-section instruction"
    )
    assert "immer als letzter Abschnitt" not in without_hist, (
        "has_historic=False must NOT add the historic-section instruction"
    )


def test_source_structure_note_positive_preamble() -> None:
    """The coverage preamble names only the source types that ARE present, in a
    positive/value-neutral frame, and never flags a missing type as a deficiency.
    Speeches-only must read as a first-class source, not a fallback."""
    from src.chatbot_async import _source_structure_note

    all_three = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=True,
        votes_present=True,
        speeches_present=True,
    )
    # Positive attribution names each present source type, joined naturally.
    assert "dem Wahlprogramm, namentlichen Abstimmungen und Reden" in all_three
    # None of the old negative "not found" clauses survive.
    assert "keine namentlichen Abstimmungen der Partei vor" not in all_three
    assert "keine Position im Wahlprogramm" not in all_three
    assert "Reden sind eine vollwertige" in all_three

    speeches_only = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=False,
        votes_present=False,
        speeches_present=True,
    )
    # Speeches-only preamble names Reden and does NOT name the absent types in the
    # preamble body (the always-present four lead-in cues before the preamble do
    # mention them, so scope the check to the text after the preamble heading).
    preamble_body = speeches_only.split("Quellen-Vorspann")[-1]
    assert "Reden" in preamble_body
    assert "Wahlprogramm" not in preamble_body
    assert "Abstimmungen" not in preamble_body

    two = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=True,
        votes_present=False,
        speeches_present=True,
    )
    assert "dem Wahlprogramm und Reden" in two

    none_present = _source_structure_note(
        "SPD",
        has_historic=False,
        manifesto_present=False,
        votes_present=False,
        speeches_present=False,
    )
    # No current source type → no coverage preamble at all.
    assert "Quellen-Vorspann" not in none_present


def test_source_structure_note_wired_into_single_party_generator() -> None:
    """generate_streaming_chatbot_response accepts the backward-compatible coverage +
    has_historic kwargs (defaults preserved). The note APPLICATION is proven
    behaviourally by the test_system_prompt_* tests below."""
    from src import chatbot_async as ca

    sig = inspect.signature(ca.generate_streaming_chatbot_response)
    assert "present_sources" in sig.parameters, "must accept 'present_sources'"
    assert sig.parameters["present_sources"].default is None, (
        "present_sources default must be None"
    )
    assert "has_historic" in sig.parameters, "must accept 'has_historic'"
    assert sig.parameters["has_historic"].default is False, (
        "has_historic default must be False"
    )


def test_comparison_generator_accepts_has_historic(monkeypatch) -> None:
    """The comparison generator accepts has_historic (default False) and, when set,
    injects the historic-marking note into the system prompt — WITHOUT the
    single-party four-section lead-ins (those are single-party only)."""
    from src import chatbot_async as ca

    sig = inspect.signature(ca.generate_streaming_chatbot_comparing_response)
    assert "has_historic" in sig.parameters, (
        "comparison generator must accept has_historic"
    )
    assert sig.parameters["has_historic"].default is False, (
        "comparison has_historic default must be False"
    )

    captured_true = _capture_system_prompt(monkeypatch)
    _run_comparison(has_historic=True)
    prompt = captured_true["system"]
    assert "immer als letzter Abschnitt" in prompt, (
        "comparison generator must apply the historic-marking note when has_historic"
    )
    # The single-party four-section lead-ins must NOT leak into the comparison prompt.
    assert "Im Wahlprogramm fordert" not in prompt, (
        "comparison path must NOT use the single-party four-section note"
    )

    captured_false = _capture_system_prompt(monkeypatch)
    _run_comparison(has_historic=False)
    assert "immer als letzter Abschnitt" not in captured_false["system"], (
        "no historic note without has_historic"
    )


# ---------------------------------------------------------------------------
# the structure note reaches the assembled SINGLE-PARTY system prompt
# (deterministic, no-network: monkeypatch stream_answer_from_llms to capture the
# SystemMessage content for a normal party — that branch makes no context/LLM call).
# ---------------------------------------------------------------------------


def _make_context_party(pid: str = "spd") -> ContextParty:
    return ContextParty(
        party_id=pid,
        name=pid.upper(),
        long_name=f"{pid.upper()} lang",
        website_url="https://example.com",
    )


def _capture_system_prompt(monkeypatch) -> dict:
    """Patch chatbot_async.stream_answer_from_llms to record the system prompt."""
    from src import chatbot_async as ca

    captured: dict = {}

    async def _fake_stream(_llms, messages, **_kwargs):
        captured["system"] = messages[0].content

        async def _gen():
            return
            yield  # pragma: no cover — makes this an (empty) async generator

        return _gen()

    monkeypatch.setattr(ca, "stream_answer_from_llms", _fake_stream)
    return captured


def _run_single_party(**gen_kwargs) -> None:
    from src import chatbot_async as ca

    asyncio.run(
        ca.generate_streaming_chatbot_response(
            _make_context_party(),
            "conv",
            "frage?",
            [],
            all_parties=[],
            chat_response_llm_size=LLMSize.LARGE,
            **gen_kwargs,
        )
    )


def _run_comparison(**gen_kwargs) -> None:
    from src import chatbot_async as ca

    party = _make_context_party()
    asyncio.run(
        ca.generate_streaming_chatbot_comparing_response(
            party,
            "conv",
            "frage?",
            {party.party_id: []},  # comparison ctx indexes docs per party
            [party],
            LLMSize.LARGE,
            **gen_kwargs,
        )
    )


def test_system_prompt_includes_four_leadins(monkeypatch) -> None:
    """A normal party call (present_sources opted in) surfaces the four German
    lead-in cues in the assembled system prompt."""
    captured = _capture_system_prompt(monkeypatch)
    _run_single_party(present_sources=(True, True, True), has_historic=False)
    system_prompt = captured["system"]
    assert "Im Wahlprogramm fordert" in system_prompt
    assert "Bei namentlichen Abstimmungen stimmte" in system_prompt
    assert "In Reden betonte" in system_prompt


def test_system_prompt_historic_conditional(monkeypatch) -> None:
    """has_historic=True adds the historic-section instruction; False omits it."""
    captured_true = _capture_system_prompt(monkeypatch)
    _run_single_party(present_sources=(True, True, True), has_historic=True)
    assert "immer als letzter Abschnitt" in captured_true["system"]

    captured_false = _capture_system_prompt(monkeypatch)
    _run_single_party(present_sources=(True, True, True), has_historic=False)
    assert "immer als letzter Abschnitt" not in captured_false["system"]


def test_system_prompt_positive_preamble(monkeypatch) -> None:
    """present_sources naming which types are present surfaces the positive coverage
    preamble; speeches-only reads as a first-class source, never a deficiency."""
    captured_all = _capture_system_prompt(monkeypatch)
    _run_single_party(present_sources=(True, True, True), has_historic=False)
    all_sp = captured_all["system"]
    assert "dem Wahlprogramm, namentlichen Abstimmungen und Reden" in all_sp
    assert "keine namentlichen Abstimmungen der Partei vor" not in all_sp

    captured_speeches = _capture_system_prompt(monkeypatch)
    _run_single_party(present_sources=(False, False, True), has_historic=False)
    speeches_sp = captured_speeches["system"]
    assert "Reden sind eine vollwertige" in speeches_sp
    # Speeches-only preamble body names Reden only, not the absent types.
    preamble_body = speeches_sp.split("Quellen-Vorspann")[-1]
    assert "Wahlprogramm" not in preamble_body
    assert "Abstimmungen" not in preamble_body


def test_system_prompt_default_no_structure_note(monkeypatch) -> None:
    """The default call (no present_sources, has_historic False) omits the structure
    note entirely — backward compatibility with untouched callers."""
    captured = _capture_system_prompt(monkeypatch)
    _run_single_party()  # no present_sources / has_historic kwargs
    system_prompt = captured["system"]
    assert "Im Wahlprogramm fordert" not in system_prompt
    assert "Quellenbewusste Struktur deiner Antwort" not in system_prompt
