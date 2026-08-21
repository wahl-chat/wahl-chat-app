# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Dispatch behaviour of the container entrypoint (no Docker build required).

Guards the regression where the ingestion Cloud Run Job booted the API server
instead of the connector: the entrypoint must run ``src.ingestion.run`` when
CONNECTOR_ID is set and the FastAPI app otherwise. We stub ``python`` on PATH so
the entrypoint's ``exec python …`` echoes its args instead of launching anything.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_ENTRYPOINT = Path(__file__).resolve().parents[1] / "docker-entrypoint.sh"


def _run(env_overrides: dict[str, str], tmp_path: Path) -> str:
    stub = tmp_path / "python"
    stub.write_text('#!/bin/sh\necho "PYTHON $*"\n')
    stub.chmod(0o755)

    env = {k: v for k, v in os.environ.items() if k != "CONNECTOR_ID"}
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env.update(env_overrides)

    result = subprocess.run(
        ["sh", str(_ENTRYPOINT)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout


def test_connector_id_dispatches_the_ingestion_runner(tmp_path: Path) -> None:
    out = _run({"CONNECTOR_ID": "abgeordnetenwatch_votes"}, tmp_path)
    assert "-m src.ingestion.run" in out
    assert "src.app" not in out


def test_no_connector_id_starts_the_api(tmp_path: Path) -> None:
    out = _run({}, tmp_path)
    assert "-m src.app" in out
    assert "src.ingestion.run" not in out
