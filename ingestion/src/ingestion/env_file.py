# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The local env file for the ingestion CLIs.

Every CLI loads it before its other imports, because COLLECTION_NAME and the
embedding settings are read at import time. Cloud Run has no .env, so the job
spec's environment is all a deployed run sees.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values, load_dotenv

_INGESTION_ROOT = Path(__file__).resolve().parents[2]

# Paths in an env file that mean "next to this file". python-dotenv leaves them
# relative, and the readers resolve them against the working directory, so a CLI
# run from ingestion/ with ai-backend/.env missed ai-backend/vertex-sa.json and
# silently billed Google AI Studio instead of Vertex.
_FILE_RELATIVE_PATHS = ("VERTEX_SA_JSON_FILE",)


def env_file_path() -> Optional[Path]:
    """ingestion/.env, else ai-backend/.env: API keys can be in either."""
    for path in (
        _INGESTION_ROOT / ".env",
        _INGESTION_ROOT.parent / "ai-backend" / ".env",
    ):
        if path.exists():
            return path
    return None


def load_env_file(path: Optional[Path] = None) -> Optional[Path]:
    """Load the env file without overriding exported variables.

    override=False keeps what make, CI or the shell exported in force. A path
    the file sets relative to itself is made absolute; an exported relative
    path is left alone, since it means the caller's working directory.
    """
    path = path or env_file_path()
    if path is None:
        return None
    exported = set(os.environ)
    load_dotenv(path, override=False)
    values = dotenv_values(path)
    for key in _FILE_RELATIVE_PATHS:
        value = (values.get(key) or "").strip()
        if key in exported or not value or Path(value).is_absolute():
            continue
        os.environ[key] = str((path.parent / value).resolve())
    return path
