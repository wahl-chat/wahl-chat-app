# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Election/party lookup for uploaded manifestos, read from the Firestore seed files.

``firebase/firestore_data/{ENV}/contexts.json`` and ``parties_{context_id}.json``
are the SAME files ``firebase/scripts/seed_firestore.py`` loads into Firestore, so
reading them here means the ingestor and the running app agree on an election's
region, level and party list without a second table to keep in sync. That file
lookup is the default: no credentials, no network, runs in CI.

Those files are absent from the container image (the Docker build context is
``ai-backend/``), so a Cloud Run Job sets ``ELECTION_FIXTURES_SOURCE=firestore`` and
reads the live database instead — see ``load_election`` and ``firestore_fixtures``.
Both backends funnel through ``build_fixture``, so the validation below is enforced
identically whichever one is in use.

Why this is a hard gate rather than a warning
---------------------------------------------
``region`` and ``party_id`` are the two fields that decide whether a chunk is ever
retrievable. Manifesto retrieval filters on the election's MOST SPECIFIC region
only (``region_path[-1]``) and on ``party_id`` as the tenant key, so a chunk
stamped ``DE-BY`` for a ``DE-BY-MUC`` election, or ``CSU`` where the context's
party doc is ``csu``, is written successfully and then never returned — a silent
coverage hole with no error anywhere. Both values are therefore derived from these
fixtures, never typed by an operator, and anything unresolvable raises.
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

    Attributes:
        context_id:    Firestore context doc id (== the upload path's election segment).
        name:          Display name, used to build citation titles.
        region:        The context's MOST SPECIFIC region (``region_path[-1]``) —
                       the only region manifesto retrieval matches on.
        level:         Governance level ("federal" | "state" | "municipal" | "eu").
        election_date: The context's ``date``, stamped as chunk ``publish_date``.
        party_ids:     Party doc ids configured for this context. Membership is
                       required; an upload for any other slug is rejected.
    """

    context_id: str
    name: str
    region: str
    level: str
    election_date: date_type
    party_ids: frozenset[str]


def fixture_dir(env: Optional[str] = None) -> Path:
    """Return the seed-data directory for *env* (defaults to ``$ENV``, else dev).

    Resolved relative to this file so it works from any cwd. The path crosses out
    of ai-backend into firebase/ because that is where the seed data lives; after
    the ingestion tree moves to a repo-root package the two become siblings.
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

    The single validation implementation, shared by BOTH backends — the file
    reader and the Firestore reader. Keeping it in one place is the point: a
    backend that skipped one of these checks would reintroduce exactly the silent
    unreachable-chunk failure the gate exists to prevent.

    Args:
        context_id: Context doc id.
        ctx:        The context's fields (JSON object or Firestore document dict).
        party_ids:  Party ids configured for this election.
        origin:     Human-readable source, quoted in error messages so an operator
                    knows WHERE to fix a bad value.

    Raises:
        FixtureLookupError: If ``region_path`` / ``level`` / ``date`` is missing or
            unusable, or no parties are configured. Nothing is defaulted.
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
    """Parse a context ``date`` into a ``date``.

    Accepts the ISO string the seed files carry and the datetime a Firestore
    timestamp deserialises to, so the same context is read identically from either
    backend.

    Raises:
        FixtureLookupError: If the value is missing or unparseable — it becomes the
            chunk publish_date, which both scopes retrieval and is shown to users.
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

    Backend is chosen by ``ELECTION_FIXTURES_SOURCE``:
      * unset / ``"files"`` (default) — the checked-in seed files. Offline, no
        credentials, runs in CI. What a local or host run uses.
      * ``"firestore"`` — the live database. What the container uses, because the
        seed files are not in the image (the build context is ai-backend/); there
        the running Firestore is also the more accurate authority.

    The switch is explicit on purpose: an automatic fallback would let a mistyped
    path quietly change which authority is trusted. A container that forgets the
    variable fails loudly with "seed file not found" instead.

    Args:
        context_id: Context doc id, e.g. ``"landtagswahl-sachsen-anhalt-2026"``.
        env:        Seed-data environment for the file backend; defaults to ``$ENV``
                    then ``"dev"``. Ignored by the Firestore backend, which reads
                    whichever project its credentials point at.

    Raises:
        FixtureLookupError: If the election cannot be resolved, or is missing any
            field that would leave its chunks unreachable. See build_fixture.
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
