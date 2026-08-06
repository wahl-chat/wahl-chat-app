# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Unit tests for the Vertex AI credential resolver (src/google_credentials.py).

Two contracts are under test, and the distinction between them is the whole
design:

  1. UNCONFIGURED degrades quietly. With no VERTEX_* credential source set,
     resolution returns None without raising and without warning, because every
     caller treats None as "fall back to Google AI Studio". A raise here would
     take down module import of src/llms.py and with it the whole service. This
     is the CI and local-dev path.

  2. MISCONFIGURED is never silent. A source that WAS supplied but is unusable
     always logs a warning, and raises VertexConfigError under VERTEX_REQUIRED.
     Silence here is the worst outcome available: the service keeps answering
     while Gemini spend keeps landing on the project this module exists to move
     it off.

No real key is used — the loading paths are exercised with malformed input and
fake credential objects. The live success path is covered in test_embeddings.py.
"""

from __future__ import annotations

import logging

import pytest

from src import google_credentials as gc

_LOGGER_NAME = "src.google_credentials"


@pytest.fixture(autouse=True)
def _clear_cache():
    """get_vertex_credentials is lru_cached; env changes need a clear.

    Guarded on teardown because several tests monkeypatch the function with a
    plain lambda, which has no cache_clear. Ordering makes the real function the
    likely target here, but not worth an AttributeError if that ever shifts.
    """
    gc.get_vertex_credentials.cache_clear()
    yield
    clear = getattr(gc.get_vertex_credentials, "cache_clear", None)
    if clear is not None:
        clear()


@pytest.fixture()
def no_vertex_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "VERTEX_SA_JSON",
        "VERTEX_SA_JSON_FILE",
        "VERTEX_PROJECT_ID",
        "VERTEX_LOCATION",
        # Cleared too: an exported value in a developer shell would otherwise
        # flip the whole suite into strict mode and fail it in confusing ways.
        "VERTEX_REQUIRED",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture()
def strict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERTEX_REQUIRED", "1")


class _KeyWithoutProject:
    """A credentials object that carries no project_id (some keys do not)."""


# ---------------------------------------------------------------------------
# Contract 1: unconfigured degrades quietly.
# ---------------------------------------------------------------------------


def test_returns_none_when_unconfigured(
    caplog: pytest.LogCaptureFixture, no_vertex_env: None
) -> None:
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert gc.get_vertex_credentials() is None
        assert gc.vertex_enabled() is False
        assert gc.vertex_project() is None

    # Nothing was configured, so there is nothing to complain about. Warning here
    # would fire on every CI run and train everyone to ignore the log line that
    # matters.
    assert caplog.records == []


def test_strict_mode_does_not_raise_when_unconfigured(
    no_vertex_env: None, strict: None
) -> None:
    """VERTEX_REQUIRED escalates BROKEN config, not ABSENT config.

    If setting the flag alone were enough to raise, it could not be set as a
    blanket default on a revision whose secret has not been wired yet — the
    service would simply fail to start.
    """
    assert gc.get_vertex_credentials() is None
    assert gc.vertex_enabled() is False


# ---------------------------------------------------------------------------
# Contract 2: misconfigured warns, and raises under VERTEX_REQUIRED.
# ---------------------------------------------------------------------------


def test_malformed_json_warns_and_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, no_vertex_env
) -> None:
    """A corrupt key must not raise by default — it falls back to AI Studio."""
    monkeypatch.setenv("VERTEX_SA_JSON", "{not valid json")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert gc.get_vertex_credentials() is None
        assert gc.vertex_enabled() is False

    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_wellformed_json_that_is_not_a_key_degrades_to_none(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """Valid JSON missing the service-account fields is still unusable."""
    monkeypatch.setenv("VERTEX_SA_JSON", '{"hello": "world"}')

    assert gc.get_vertex_credentials() is None


def test_blank_sa_json_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, no_vertex_env
) -> None:
    """`VERTEX_SA_JSON=` used to fall through both branches unreported.

    It is neither truthy-after-strip nor a path, so resolution reached the final
    `return None` having logged nothing at all — indistinguishable from a machine
    where Vertex was never configured.
    """
    monkeypatch.setenv("VERTEX_SA_JSON", "   ")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert gc.get_vertex_credentials() is None

    assert "VERTEX_SA_JSON is set but empty" in caplog.text


def test_missing_file_path_warns_with_absolute_path(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, no_vertex_env
) -> None:
    """The resolved absolute path is the point of the message.

    The documented form is a path relative to the process CWD, so "wrong CWD" is
    the likely mistake and the relative string alone does not reveal it.
    """
    monkeypatch.setenv("VERTEX_SA_JSON_FILE", "nope/vertex-sa.json")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert gc.get_vertex_credentials() is None

    assert "does not exist" in caplog.text
    assert "/nope/vertex-sa.json" in caplog.text  # absolute, not as supplied


def test_blank_sa_json_does_not_disable_a_working_file(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    no_vertex_env: None,
    tmp_path,
) -> None:
    """A leftover `VERTEX_SA_JSON=` must not veto the file form.

    Both variables set, with the raw one blank, is a realistic .env state. The
    blank value is still worth a warning, but it must not shadow the source that
    actually works.
    """
    key = tmp_path / "vertex-sa.json"
    key.write_text('{"hello": "world"}')  # unusable content, but it EXISTS
    monkeypatch.setenv("VERTEX_SA_JSON", "")
    monkeypatch.setenv("VERTEX_SA_JSON_FILE", str(key))

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        gc.get_vertex_credentials()

    assert "VERTEX_SA_JSON is set but empty" in caplog.text
    # It proceeded to the file rather than bailing out at the blank value.
    assert "could not be loaded" in caplog.text


def test_blank_sa_json_beside_working_file_does_not_raise_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None, strict: None, tmp_path
) -> None:
    """Strict mode asks "is Vertex unusable?" — a shadowed blank value is not that.

    Escalating here would take a revision down over a variable that changes
    nothing.
    """
    key = tmp_path / "vertex-sa.json"
    key.write_text("{}")
    monkeypatch.setenv("VERTEX_SA_JSON", "")
    monkeypatch.setenv("VERTEX_SA_JSON_FILE", str(key))

    # The key content is junk, so this still fails — but via the load path, and
    # the blank-value finding alone did not raise before reaching it.
    with pytest.raises(gc.VertexConfigError, match="could not be loaded"):
        gc.get_vertex_credentials()


@pytest.mark.parametrize(
    ("env", "value", "match"),
    [
        ("VERTEX_SA_JSON", "   ", "set but empty"),
        ("VERTEX_SA_JSON", "{not valid json", "could not be loaded"),
        ("VERTEX_SA_JSON", '{"hello": "world"}', "could not be loaded"),
        ("VERTEX_SA_JSON_FILE", "/nonexistent/vertex-sa.json", "does not exist"),
    ],
)
def test_strict_mode_raises_on_every_misconfiguration(
    monkeypatch: pytest.MonkeyPatch,
    no_vertex_env: None,
    strict: None,
    env: str,
    value: str,
    match: str,
) -> None:
    monkeypatch.setenv(env, value)

    with pytest.raises(gc.VertexConfigError, match=match):
        gc.get_vertex_credentials()


def test_credentials_without_resolvable_project_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, no_vertex_env
) -> None:
    """The third silent path: a key that loads but yields no project id.

    vertex_project() returns None, so VERTEX_AVAILABLE ends up False in
    src/llms.py — previously with nothing logged anywhere.
    """
    monkeypatch.setattr(gc, "get_vertex_credentials", lambda: _KeyWithoutProject())

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        assert gc.vertex_enabled() is False

    assert "no project id could be resolved" in caplog.text


def test_credentials_without_resolvable_project_raises_in_strict_mode(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None, strict: None
) -> None:
    monkeypatch.setattr(gc, "get_vertex_credentials", lambda: _KeyWithoutProject())

    with pytest.raises(gc.VertexConfigError, match="no project id"):
        gc.vertex_enabled()


# ---------------------------------------------------------------------------
# Location and project resolution.
# ---------------------------------------------------------------------------


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


def test_project_env_rescues_a_key_without_project_id(
    monkeypatch: pytest.MonkeyPatch, no_vertex_env: None
) -> None:
    """The explicit variable is the documented fix for the warning above."""
    monkeypatch.setattr(gc, "get_vertex_credentials", lambda: _KeyWithoutProject())
    monkeypatch.setenv("VERTEX_PROJECT_ID", "billing-project")

    assert gc.vertex_enabled() is True
