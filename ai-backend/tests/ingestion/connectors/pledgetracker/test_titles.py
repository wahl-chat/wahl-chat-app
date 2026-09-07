# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Short-headline generation unit tests (LLM faked via the injectable hook).

Tests defined here:
  - test_headlines_set_in_order: one batched call fills event_short in order and
    the prompt carries the pledge claim as context.
  - test_count_mismatch_keeps_full_texts: wrong headline count → no titles set.
  - test_llm_error_is_soft: an LLM exception never propagates; 0 titles added.
  - test_only_missing_events_are_sent: events that already carry a headline are
    untouched and excluded from the prompt (backfill semantics).
"""

from __future__ import annotations

from src.ingestion.connectors.pledgetracker.connector import PledgeTrackerConnector
from src.ingestion.connectors.pledgetracker.registry import PledgeInput
from src.ingestion.connectors.pledgetracker.titles import add_short_titles
from src.models.pledge_tracker import PledgeRecord
from src.models.structured_outputs import PledgeEventHeadlines


def _record() -> PledgeRecord:
    connector = PledgeTrackerConnector(stub=True)
    return connector.merge_result(
        PledgeInput(
            claim="Wir wollen, dass die A14 fertig wird",
            pledge_date="2021-03-27",
            pledge_author="CDU",
            bundesland="Sachsen-Anhalt",
        ),
        {
            "status": "success",
            "events": [
                {"date": "2026-01-05", "event": "Langer Satz über DEGES-Ausschreibungen.", "label": "Ja"},
                {"date": "2025-06-01", "event": "Langer Satz über den Planungsstand der A143.", "label": "Ja"},
            ],
        },
    )


class _FakeStructuredOutput:
    def __init__(self, headlines: list[str] | None = None, error: bool = False):
        self._headlines = headlines if headlines is not None else []
        self._error = error
        self.prompts: list[str] = []

    async def __call__(self, messages) -> PledgeEventHeadlines:  # noqa: ANN001
        self.prompts.append(messages[0].content)
        if self._error:
            raise RuntimeError("LLM unavailable")
        return PledgeEventHeadlines(headlines=self._headlines)


def test_headlines_set_in_order() -> None:
    """The batched call fills event_short in order; the claim is prompt context."""
    record = _record()
    fake = _FakeStructuredOutput(
        headlines=["DEGES schreibt Bauarbeiten aus", "Planungsstand der A143"]
    )

    added = add_short_titles(record, _structured_output_fn=fake)

    assert added == 2
    assert record.timeline_events[0].event_short == "DEGES schreibt Bauarbeiten aus"
    assert record.timeline_events[1].event_short == "Planungsstand der A143"
    assert record.claim in fake.prompts[0]


def test_count_mismatch_keeps_full_texts() -> None:
    """Wrong headline count → nothing is set (UI falls back to full text)."""
    record = _record()
    added = add_short_titles(
        record, _structured_output_fn=_FakeStructuredOutput(headlines=["nur eine"])
    )
    assert added == 0
    assert all(e.event_short is None for e in record.timeline_events)


def test_llm_error_is_soft() -> None:
    """An LLM exception never propagates out of add_short_titles."""
    record = _record()
    added = add_short_titles(
        record, _structured_output_fn=_FakeStructuredOutput(error=True)
    )
    assert added == 0
    assert all(e.event_short is None for e in record.timeline_events)


def test_only_missing_events_are_sent() -> None:
    """Events with an existing headline are untouched and excluded (backfill)."""
    record = _record()
    record.timeline_events[0].event_short = "Bereits vorhanden"
    fake = _FakeStructuredOutput(headlines=["Neue Schlagzeile"])

    added = add_short_titles(record, _structured_output_fn=fake)

    assert added == 1
    assert record.timeline_events[0].event_short == "Bereits vorhanden"
    assert record.timeline_events[1].event_short == "Neue Schlagzeile"
    assert "A143" in fake.prompts[0]
    assert "DEGES" not in fake.prompts[0]
