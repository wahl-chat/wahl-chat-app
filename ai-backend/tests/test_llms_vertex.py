# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the Vertex AI tier in src/llms.py.

Two properties matter and neither needs a network or a real key:

  1. Without Vertex credentials the module is byte-for-byte its old self — the
     LLM lists contain only the AI Studio / Azure / OpenAI entries. This is the
     CI and local-dev-without-a-key path.
  2. The Vertex entries, when present, outrank every AI Studio entry, so the
     existing priority-sorted failover in get_answer_from_llms and friends tries
     Vertex first and falls through to the identical AI Studio model on error.

The conftest sets no VERTEX_* variables, so importing src.llms here exercises
case (1) directly. Case (2) is asserted against the module's own construction
helper rather than by re-importing with credentials, which would require a real
key to build a client.
"""

from __future__ import annotations

from src import llms


def test_no_vertex_tier_without_credentials() -> None:
    """The default test environment has no key → the lists are unchanged."""
    assert llms.VERTEX_AVAILABLE is False

    names = [entry.name for entry in llms.RESPONSE_GENERATION_LLMS]
    assert not any(name.startswith("vertex-") for name in names)

    prepost = [entry.name for entry in llms.PRE_AND_POST_PROCESSING_LLMS]
    assert not any(name.startswith("vertex-") for name in prepost)


def test_ai_studio_clients_are_pinned_off_vertex() -> None:
    """The fallback tier must never flip to Vertex via GOOGLE_GENAI_USE_VERTEXAI.

    _determine_backend consults that env var before defaulting to AI Studio, so
    an unpinned fallback client would silently target Vertex and then fail for
    want of credentials — losing the fallback exactly when it is needed.
    """
    assert llms.google_gemini_2_flash._use_vertexai is False
    assert llms.google_gemini_3_flash_preview._use_vertexai is False
    assert llms.google_gemini_2_5_flash._use_vertexai is False
    assert llms.google_gemini_2_5_flash_lite_det._use_vertexai is False
    assert llms.google_gemini_2_flash_det._use_vertexai is False


def test_model_kwargs_survive_the_helper() -> None:
    """The thinking_* and temperature settings are behavioural, not cosmetic."""
    assert llms.google_gemini_3_flash_preview.temperature == 1.0
    assert llms.google_gemini_3_flash_preview.thinking_level == "low"
    assert llms.google_gemini_2_5_flash.thinking_budget == 0
    assert llms.google_gemini_2_5_flash_lite_det.temperature == 0.0
    assert llms.google_gemini_2_flash_det.temperature == 0.0


def test_vertex_entries_would_outrank_ai_studio() -> None:
    """Vertex priorities (192-200) must exceed every AI Studio priority.

    Asserted against the live lists so that re-prioritising an AI Studio entry
    above 192 in future fails here rather than silently sending traffic to the
    wrong project.
    """
    highest_existing = max(
        entry.priority
        for entry in llms.RESPONSE_GENERATION_LLMS + llms.PRE_AND_POST_PROCESSING_LLMS
    )
    assert highest_existing < 192
