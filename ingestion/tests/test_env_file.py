# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import os
from pathlib import Path

import pytest

from ingestion.env_file import load_env_file

_KEY = "VERTEX_SA_JSON_FILE"


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Another directory as cwd: the case that used to miss the key.
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "ai-backend"
    folder.mkdir()
    for key in (_KEY, "WAHLCHAT_ENV_FILE_TEST"):
        monkeypatch.delenv(key, raising=False)
    return folder


def test_a_relative_key_path_is_read_next_to_the_env_file(env_dir: Path) -> None:
    env = env_dir / ".env"
    env.write_text(f"{_KEY}=vertex-sa.json\nWAHLCHAT_ENV_FILE_TEST=1\n")
    try:
        assert load_env_file(env) == env
        assert os.environ[_KEY] == str(env_dir.resolve() / "vertex-sa.json")
        assert os.environ["WAHLCHAT_ENV_FILE_TEST"] == "1"
    finally:
        os.environ.pop(_KEY, None)
        os.environ.pop("WAHLCHAT_ENV_FILE_TEST", None)


def test_an_absolute_key_path_is_kept(env_dir: Path) -> None:
    env = env_dir / ".env"
    env.write_text(f"{_KEY}=/keys/vertex-sa.json\n")
    try:
        load_env_file(env)
        assert os.environ[_KEY] == "/keys/vertex-sa.json"
    finally:
        os.environ.pop(_KEY, None)


def test_an_exported_key_path_wins_and_stays_as_given(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = env_dir / ".env"
    env.write_text(f"{_KEY}=vertex-sa.json\n")
    monkeypatch.setenv(_KEY, "exported/vertex-sa.json")
    load_env_file(env)
    assert os.environ[_KEY] == "exported/vertex-sa.json"
