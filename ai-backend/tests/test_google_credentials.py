# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for the Vertex AI credential resolver (src/google_credentials.py).

The contract under test is degradation: absent or unusable credentials must
resolve to None rather than raising, because every caller treats None as
"fall back to Google AI Studio". A raise here would take down module import of
src/llms.py and with it the whole service.

No real key is used — the JSON-parsing path is exercised with malformed input,
and the success path is covered in test_embeddings.py with a fake credentials
object.
"""

from __future__ import annotations

import pytest

from src import google_credentials as gc


@pytest.fixture(autouse=True)
def _clear_cache():
    """get_vertex_credentials is lru_cached; env changes need a clear."""
    gc.get_vertex_credentials.cache_clear()
    yield
    gc.get_vertex_credentials.cache_clear()


@pytest.fixture()
def no_vertex_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "VERTEX_SA_JSON",
        "VERTEX_SA_JSON_FILE",
        "VERTEX_PROJECT_ID",
        "VERTEX_LOCATION",
    ):
        monkeypatch.delenv(name, raising=False)


def test_returns_none_when_unconfigured(no_vertex_env: None) -> None:
    assert gc.get_vertex_credentials() is None
    assert gc.vertex_enabled() is False
    assert gc.vertex_project() is None


def test_malformed_json_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """A corrupt key must not raise — it must fall back to AI Studio."""
    monkeypatch.setenv("VERTEX_SA_JSON", "{not valid json")

    assert gc.get_vertex_credentials() is None
    assert gc.vertex_enabled() is False


def test_wellformed_json_that_is_not_a_key_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """Valid JSON missing the service-account fields is still unusable."""
    monkeypatch.setenv("VERTEX_SA_JSON", '{"hello": "world"}')

    assert gc.get_vertex_credentials() is None


def test_missing_file_path_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    monkeypatch.setenv("VERTEX_SA_JSON_FILE", "/nonexistent/vertex-sa.json")

    assert gc.get_vertex_credentials() is None


def test_location_defaults_to_global(no_vertex_env: None) -> None:
    """The default is "global" and that is load-bearing, so pin it.

    Regional endpoints on the billing project 404 on gemini-embedding-2 and on
    every chat model except gemini-2.5-flash, and a 404 falls through to AI
    Studio silently — so a well-meaning change to a regional value here would
    quietly stop most traffic from being billed to Vertex at all.
    """
    assert gc.vertex_location() == "global"


def test_location_env_override(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    monkeypatch.setenv("VERTEX_LOCATION", "us-central1")

    assert gc.vertex_location() == "us-central1"


def test_blank_env_values_fall_back_to_defaults(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """`VERTEX_LOCATION=` must not yield an empty region.

    A blank value is easy to leave behind in a shell or a Cloud Run env spec, and
    passing "" through to the client fails obscurely rather than loudly.
    """
    monkeypatch.setenv("VERTEX_LOCATION", "   ")
    monkeypatch.setenv("VERTEX_PROJECT_ID", "  ")

    assert gc.vertex_location() == "global"
    assert gc.vertex_project() is None


def test_project_env_wins_without_credentials(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """VERTEX_PROJECT_ID resolves even when no key is present, but that alone
    is not enough to enable Vertex — credentials are also required."""
    monkeypatch.setenv("VERTEX_PROJECT_ID", "billing-project")

    assert gc.vertex_project() == "billing-project"
    assert gc.vertex_enabled() is False
