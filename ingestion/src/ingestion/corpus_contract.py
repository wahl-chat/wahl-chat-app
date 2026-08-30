# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

# GENERATED-PAIR — duplicated in ai-backend/src/ and ingestion/src/ingestion/.
# Edit both; scripts/check_contract_parity.py enforces it.

"""Reader for ``corpus-contract.json``, the only file this package shares with
``ai-backend/`` (see AGENTS.md for why the two are independent).

Found by walking up from this module, so it resolves in the repo and in the image
alike; CORPUS_CONTRACT_PATH overrides. Values needing static types (the enums in ``schemas.py``)
stay hand-written and are covered by a parity test instead.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTRACT_FILENAME = "corpus-contract.json"


def _find_contract() -> Path:
    """Locate corpus-contract.json, or raise with the paths that were tried."""
    override = os.getenv("CORPUS_CONTRACT_PATH")
    if override:
        path = Path(override)
        if not path.is_file():
            raise RuntimeError(
                f"CORPUS_CONTRACT_PATH points at {path}, which does not exist."
            )
        return path

    searched = []
    for parent in Path(__file__).resolve().parents:
        candidate = parent / CONTRACT_FILENAME
        searched.append(str(candidate))
        if candidate.is_file():
            return candidate

    raise RuntimeError(
        f"{CONTRACT_FILENAME} not found. It is the shared corpus contract and must "
        "be present at the repo root (or copied into the image next to the package "
        f"directories). Set CORPUS_CONTRACT_PATH to override. Searched: {searched}"
    )


@lru_cache(maxsize=1)
def contract() -> dict[str, Any]:
    """Parsed contract, cached for the process lifetime."""
    return json.loads(_find_contract().read_text(encoding="utf-8"))


def section(name: str) -> Any:
    """One top-level section. Raises rather than defaulting — a missing section
    means the contract and this code are from different revisions."""
    data = contract()
    if name not in data:
        raise KeyError(
            f"{CONTRACT_FILENAME} has no '{name}' section (found: {sorted(data)}). "
            "The contract file and this package are out of sync."
        )
    return data[name]
