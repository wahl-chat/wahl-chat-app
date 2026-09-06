# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Tests for the Vertex AI tier in src/llms.py.

Two properties matter and neither needs a network or a real key:

  1. Without Vertex credentials the module is byte-for-byte its old self — the
     LLM lists contain only the AI Studio / OpenAI entries. This is the
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
    assert names == [
        "google-gemini-3.6-flash",
        "openai-gpt-5.6-terra",
        "google-gemini-3.7-flash",
        "google-gemini-3-flash-preview",
        "google-gemini-3.5-flash",
    ]

    prepost = [entry.name for entry in llms.PRE_AND_POST_PROCESSING_LLMS]
    assert not any(name.startswith("vertex-") for name in prepost)
    assert prepost == [
        "google-gemini-3.1-flash-lite",
        "openai-gpt-5.6-luna",
        "google-gemini-2.5-flash-lite",
        "google-gemini-3.5-flash-lite",
    ]


def _ai_studio_gemini_clients():
    return [
        entry.model
        for entry in llms.RESPONSE_GENERATION_LLMS + llms.PRE_AND_POST_PROCESSING_LLMS
        if entry.name.startswith("google-gemini-")
    ]


def test_ai_studio_clients_are_pinned_off_vertex() -> None:
    """The fallback tier must never flip to Vertex via GOOGLE_GENAI_USE_VERTEXAI.

    _determine_backend consults that env var before defaulting to AI Studio, so
    an unpinned fallback client would silently target Vertex and then fail for
    want of credentials — losing the fallback exactly when it is needed.

    Asserted on `vertexai` (the explicit pin) as well as on the resolved
    `_use_vertexai`: the resolved value would also read False with the kwarg
    dropped and the env var absent, so it alone does not prove the pin is there.
    """
    for client in _ai_studio_gemini_clients():
        assert client.vertexai is False, client.model
        assert client._use_vertexai is False, client.model


def test_vertex_clients_are_pinned_on_vertex() -> None:
    """The other half of the pin, and the one the review asked about.

    Backend resolution puts GOOGLE_GENAI_USE_VERTEXAI *above* the "credentials
    imply Vertex" inference, so GOOGLE_GENAI_USE_VERTEXAI=false would drop an
    unpinned Vertex client onto AI Studio carrying no API key at all.

    Built through the module's own helper rather than by re-importing with
    credentials, which would need a real key.
    """
    client = llms._gemini("gemini-3.6-flash", vertex=True)

    assert client.vertexai is True
    assert client._use_vertexai is True


def test_model_kwargs_survive_the_helper() -> None:
    """The thinking_* and temperature settings are behavioural, not cosmetic."""
    assert llms.google_gemini_3_6_flash.temperature == 1.0
    assert llms.google_gemini_3_6_flash.thinking_level == "minimal"
    assert llms.google_gemini_3_7_flash.temperature == 1.0
    assert llms.google_gemini_3_7_flash.thinking_level == "low"
    assert llms.google_gemini_3_flash_preview.temperature == 1.0
    assert llms.google_gemini_3_flash_preview.thinking_level == "minimal"
    assert llms.google_gemini_3_5_flash.temperature == 1.0
    assert llms.google_gemini_3_5_flash.thinking_level == "minimal"
    assert llms.openai_gpt_5_6_terra.temperature == 1.0
    assert llms.openai_gpt_5_6_terra.reasoning_effort == "minimal"

    assert llms.google_gemini_3_1_flash_lite.temperature == 1.0
    assert llms.google_gemini_3_1_flash_lite.thinking_level == "minimal"
    assert llms.google_gemini_2_5_flash_lite.temperature == 1.0
    assert llms.google_gemini_2_5_flash_lite.thinking_budget == 0
    assert llms.google_gemini_3_5_flash_lite.temperature == 1.0
    assert llms.google_gemini_3_5_flash_lite.thinking_level == "minimal"
    assert llms.openai_gpt_5_6_luna.temperature == 1.0
    assert llms.openai_gpt_5_6_luna.reasoning_effort == "minimal"


def test_vertex_entries_would_outrank_ai_studio() -> None:
    """Vertex priorities (170-200) must exceed every AI Studio / OpenAI priority.

    Asserted against the live lists so that re-prioritising an AI Studio entry
    above 170 in future fails here rather than silently sending traffic to the
    wrong project.
    """
    highest_existing = max(
        entry.priority
        for entry in llms.RESPONSE_GENERATION_LLMS + llms.PRE_AND_POST_PROCESSING_LLMS
    )
    assert highest_existing < 170
