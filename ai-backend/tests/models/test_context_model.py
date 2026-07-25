# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the Context.legislature_period_id field.

The Context model must accept an optional ``legislature_period_id`` field
in ``src/models/context.py``.
"""

from __future__ import annotations

from src.models.context import Context


def _base_context_kwargs() -> dict:
    """Minimal kwargs to construct a valid Context (no legislature_period_id)."""
    return {
        "context_id": "bundestagswahl-2025",
        "name": "Bundestagswahl 2025",
        "short_name": "BTW 2025",
        "type": "election",
        "date": None,
        "location_name": "Deutschland",
        "is_active": True,
        "icon_url": None,
        "supports_swiper": True,
        "supports_voting_behavior": True,
        "relevant_area": None,
    }


class TestContextLegislaturePeriodId:
    """Context model must accept an optional legislature_period_id field."""

    def test_context_accepts_legislature_period_id(self) -> None:
        """Context(**kwargs, legislature_period_id=161) must set the field correctly.

        If Context does not define legislature_period_id, the extra field is
        silently dropped by Pydantic (default extra='ignore'), so accessing
        ctx.legislature_period_id would raise AttributeError.
        """
        ctx = Context(**_base_context_kwargs(), legislature_period_id=161)
        assert ctx.legislature_period_id == 161, (
            "legislature_period_id=161 was passed to Context constructor but "
            "ctx.legislature_period_id did not return 161. "
            "Add legislature_period_id: Optional[int] = Field(None, ...) to Context."
        )

    def test_context_legislature_period_id_default_is_none(self) -> None:
        """Context without legislature_period_id must default to None."""
        ctx = Context(**_base_context_kwargs())
        assert ctx.legislature_period_id is None, (
            "Context.legislature_period_id must default to None when not supplied. "
            "Add legislature_period_id: Optional[int] = Field(None, ...) to Context."
        )
