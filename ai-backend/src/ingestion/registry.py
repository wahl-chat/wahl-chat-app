# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Connector registry — flat ``{connector_id: factory}`` map.

This module is the single place that names the runnable connector IDs
and their zero-arg factory functions.  The runner (run.py) looks up a
connector by ID here and calls the factory to get an instance.

The runner does inline embed+upsert; no separate embedding_worker is needed.
AW is the canonical VOTE_RECORD producer.

bundestag_speeches is registered as a live incremental connector; it
fetches plenary speeches from the DIP Bundestag API.

Design:
    - Registered IDs:
        "abgeordnetenwatch_votes" → AbgeordnetenwatchVotesConnector
        "manifestos"              → ManifestoConnector (party_manifesto corpus)
        "bundestag_speeches"      → BundestagSpeechesConnector

    - Factories use DEFERRED imports (import happens INSIDE the factory body,
      not at module top-level).  This means importing registry.py has zero
      side effects.

    - The registry is a CLOSED dict of known IDs.  Unknown IDs are
      rejected by the caller (run.py) with a clear error.  There is no
      dynamic import of caller-supplied module paths.

Usage::

    from src.ingestion import registry

    factory = registry.CONNECTOR_FACTORIES["abgeordnetenwatch_votes"]
    connector = factory()          # AbgeordnetenwatchVotesConnector instance
"""

from __future__ import annotations

from typing import Callable

from src.ingestion.connector import BaseConnector


def _abgeordnetenwatch_votes_factory() -> BaseConnector:
    """Return an AbgeordnetenwatchVotesConnector instance (deferred import)."""
    from src.ingestion.connectors.abgeordnetenwatch.connector import AbgeordnetenwatchVotesConnector  # noqa: PLC0415

    return AbgeordnetenwatchVotesConnector()


def _manifestos_factory() -> BaseConnector:
    """Return a ManifestoConnector instance (deferred import).

    Standard cursor-based embed path via run.py.  The bespoke local-dev workflow
    (flags + Firestore backfill) lives in connectors.manifestos.bulk.
    """
    from src.ingestion.connectors.manifestos.connector import ManifestoConnector  # noqa: PLC0415

    return ManifestoConnector()


def _bundestag_speeches_factory() -> BaseConnector:
    """Return a BundestagSpeechesConnector instance (deferred import).

    Live incremental connector: DIP Bundestag API → parliamentary_speech ChunkRecords.
    The bespoke --from-jsonl backfill path lives in connectors.bundestag_speeches.bulk.
    Requires DIP_API_KEY to be set in the environment (raises RuntimeError otherwise).
    """
    from src.ingestion.connectors.bundestag_speeches.connector import BundestagSpeechesConnector  # noqa: PLC0415

    return BundestagSpeechesConnector()


def _openparliament_tv_factory() -> BaseConnector:
    """Return an OpenParliamentTvConnector instance (deferred import).

    Live incremental connector: keyless openparliament.tv GitHub bulk →
    parliamentary_speech ChunkRecords with source="op" and a video sentence_map.
    Coexists with bundestag_speeches (source="dip"), deduping downstream on
    speech_key. The bespoke --from-github backfill path lives in
    connectors.openparliament_tv.bulk. No API key required (keyless bulk path).
    """
    from src.ingestion.connectors.openparliament_tv.connector import OpenParliamentTvConnector  # noqa: PLC0415

    return OpenParliamentTvConnector()


# ---------------------------------------------------------------------------
# CONNECTOR_FACTORIES — the closed registry (no dynamic module path).
# ---------------------------------------------------------------------------

CONNECTOR_FACTORIES: dict[str, Callable] = {
    "abgeordnetenwatch_votes": _abgeordnetenwatch_votes_factory,
    "manifestos": _manifestos_factory,
    "bundestag_speeches": _bundestag_speeches_factory,
    "openparliament_tv": _openparliament_tv_factory,
}
