# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Election/party lookup for uploaded manifestos, read from the Firestore seed files
(``firebase/firestore_data/{ENV}/contexts.json`` + ``parties_{context_id}.json`` —
the same files that seed Firestore, so the ingestor agrees with the running app).

Not in the container image (build context is ``ai-backend/``), so a Cloud Run Job
sets ``ELECTION_FIXTURES_SOURCE=firestore`` instead (see ``firestore_fixtures``);
both backends funnel through ``build_fixture`` for identical validation.

This is a hard gate, not a warning: ``region``/``party_id`` decide whether a chunk
is ever retrievable (retrieval filters on ``region_path[-1]`` + party as tenant
key), so a wrong value here is a silent coverage hole with no error anywhere.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Governance levels a context may declare. Mirrors Context.level.
from src.ingestion.governance_levels import EU, FEDERAL, MUNICIPAL, STATE

_VALID_LEVELS = frozenset({FEDERAL, STATE, MUNICIPAL, EU})

# Selects the lookup backend: "files" (default) or "firestore". See load_election.
_SOURCE_ENV = "ELECTION_FIXTURES_SOURCE"


class FixtureLookupError(ValueError):
    """An election/party could not be resolved from the seed fixtures.

    A ValueError subclass so ``normalize()`` raising it is treated as a per-item
    skip by the runner rather than aborting the whole run.
    """


@dataclass(frozen=True)
class ElectionFixture:
    """Everything an uploaded manifesto needs from its election context.

    ``region`` is already ``region_path[-1]`` (the only region retrieval matches
    on); ``election_date`` becomes the chunk ``publish_date``; ``party_ids`` is the
    membership list — an upload for any other slug is rejected.
    """

    context_id: str
    name: str
    region: str
    level: str
    election_date: date_type
    party_ids: frozenset[str]


def fixture_dir(env: Optional[str] = None) -> Path:
    """Return the seed-data directory for *env* (defaults to ``$ENV``, else dev).

    Resolved relative to this file so it works from any cwd.
    """
    resolved = (env or os.getenv("ENV") or "dev").strip().lower()
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "firebase" / "firestore_data" / resolved


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FixtureLookupError(f"seed file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureLookupError(f"could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise FixtureLookupError(f"{path} must contain a JSON object")
    return data


@lru_cache(maxsize=8)
def _contexts(env: Optional[str]) -> dict:
    return _load_json(fixture_dir(env) / "contexts.json")


@lru_cache(maxsize=64)
def _parties(env: Optional[str], context_id: str) -> dict:
    return _load_json(fixture_dir(env) / f"parties_{context_id}.json")


def build_fixture(
    context_id: str,
    ctx: dict,
    party_ids: frozenset[str],
    origin: str,
) -> ElectionFixture:
    """Validate one context's fields and build its ElectionFixture.

    Shared by both backends (file + Firestore readers) so neither can skip a check
    and reintroduce the silent unreachable-chunk failure this gate prevents.
    ``origin`` is quoted in error messages so an operator knows where to fix a bad
    value. Raises FixtureLookupError; nothing is defaulted.
    """
    region_path = ctx.get("region_path")
    if not isinstance(region_path, list) or not region_path:
        raise FixtureLookupError(
            f"context {context_id!r} has no region_path — manifesto retrieval "
            "filters on its last element, so chunks would be scoped to federal "
            "'DE' and never returned for this election"
        )
    region = region_path[-1]
    if not isinstance(region, str) or not region.strip():
        raise FixtureLookupError(
            f"context {context_id!r} has a non-string region_path entry: {region!r}"
        )

    level = ctx.get("level")
    if level not in _VALID_LEVELS:
        raise FixtureLookupError(
            f"context {context_id!r} has level={level!r}; expected one of "
            f"{sorted(_VALID_LEVELS)}. Without it a sub-federal election is "
            "treated as federal at query time"
        )

    election_date = _coerce_date(context_id, ctx.get("date"))

    if not party_ids:
        raise FixtureLookupError(
            f"{origin} declares no parties for election {context_id!r}"
        )

    return ElectionFixture(
        context_id=context_id,
        name=str(ctx.get("name") or context_id),
        region=region.strip(),
        level=str(level),
        election_date=election_date,
        party_ids=party_ids,
    )


def _coerce_date(context_id: str, raw: object) -> date_type:
    """Parse a context ``date`` (ISO string or Firestore timestamp) into a ``date``.

    Raises FixtureLookupError if missing/unparseable — it becomes the chunk
    publish_date, which scopes retrieval and is shown to users.
    """
    if not raw:
        raise FixtureLookupError(
            f"context {context_id!r} has no date — it is the chunk publish_date"
        )
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date_type):
        return raw
    try:
        return date_type.fromisoformat(str(raw)[:10])
    except ValueError as exc:
        raise FixtureLookupError(
            f"context {context_id!r} has an unparseable date {raw!r}"
        ) from exc


def _load_from_files(context_id: str, env: Optional[str]) -> ElectionFixture:
    """Resolve an election from the checked-in seed files."""
    contexts = _contexts(env)
    ctx = contexts.get(context_id)
    if ctx is None:
        raise FixtureLookupError(
            f"unknown election {context_id!r} — not in contexts.json "
            f"(known: {', '.join(sorted(contexts)) or 'none'})"
        )
    return build_fixture(
        context_id,
        ctx,
        frozenset(_parties(env, context_id)),
        origin=f"parties_{context_id}.json",
    )


def load_election(context_id: str, env: Optional[str] = None) -> ElectionFixture:
    """Resolve one election's retrieval-critical metadata.

    Backend is ``ELECTION_FIXTURES_SOURCE``: unset/``"files"`` (default, local seed
    files) or ``"firestore"`` (live database — what the container uses, since the
    seed files aren't in the image). No auto-fallback: a container that forgets the
    variable fails loudly with "seed file not found" instead of silently switching
    authority.
    """
    source = (os.getenv(_SOURCE_ENV) or "files").strip().lower()
    if source == "files":
        return _load_from_files(context_id, env)
    if source == "firestore":
        # Imported lazily: the file backend must not pull in a Firestore client
        # (nor require credentials) just to read a JSON file.
        from src.ingestion.connectors.manifesto_uploads.firestore_fixtures import (  # noqa: PLC0415
            load_election_from_firestore,
        )

        return load_election_from_firestore(context_id)
    raise FixtureLookupError(
        f"{_SOURCE_ENV}={source!r} is not a known backend; expected 'files' or 'firestore'"
    )


def require_party(fixture: ElectionFixture, party_id: str) -> str:
    """Return *party_id* unchanged, or raise if it is not a party of this election.

    The tenant key must match the context's party doc id exactly — a near-miss
    ("CSU", "csu-muenchen") produces chunks no tenant-filtered query can reach.

    Raises:
        FixtureLookupError: If the slug is not configured for this election.
    """
    if party_id in fixture.party_ids:
        return party_id
    near = sorted(p for p in fixture.party_ids if p.lower() == party_id.lower())
    hint = f" (did you mean {near[0]!r}?)" if near else ""
    raise FixtureLookupError(
        f"party {party_id!r} is not configured for election "
        f"{fixture.context_id!r}{hint} — known: {', '.join(sorted(fixture.party_ids))}"
    )
