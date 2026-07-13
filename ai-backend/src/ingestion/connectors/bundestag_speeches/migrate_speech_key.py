# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
One-off migration: stamp ``speech_key`` + ``source="dip"`` onto the ~26k legacy
WP20+21 DIP ``parliamentary_speech`` chunks that predate this phase (D-07/D-11).

Why this exists (Pitfall 2 + Pitfall 4, 11-RESEARCH):
  * Legacy DIP chunks were written BEFORE the shared ``speech_key`` / ``source``
    discriminator existed. They carry ``meta.protocol_id`` + ``meta.speaker_name``
    but store NO agenda, so the agenda-bearing ``speech_key`` cannot be recovered
    from stored payload alone (Pitfall 2). We therefore RE-PARSE each protocol's
    XML to recover ``xml_rede_id → agenda_top_id`` and compute the byte-identical
    shared key via ``corpus_mapper.compute_speech_key`` — the SAME helper the live
    DIP connector uses (parity guaranteed).
  * Until every legacy chunk carries ``source="dip"``, ``get_cursor(source="dip")``
    returns ``None`` and the first source-scoped DIP run re-backfills the entire
    legislature from scratch (Pitfall 4). This migration MUST run — and be
    human-verified — BEFORE the first source-scoped DIP run.

What it does NOT do:
  * It never recomputes vectors. There is NO OpenAI call, NO vector write. It
    uses ``qdrant.set_payload`` to stamp two payload fields onto existing points
    (0 OpenAI tokens — the "cheap set_payload path").

Graceful degradation (A6 / D-07):
  * Where a protocol's XML is unavailable/unparseable, the affected redes keep a
    NO-AGENDA ``speech_key`` (empty agenda component) and the event is logged.
  * Where wahlperiode / session cannot be parsed, ``speech_key`` is left unset for
    that speech (still stamps ``source="dip"`` so the cursor guard holds) and the
    event is logged.

Idempotency:
  * The scroll filter selects only chunks that LACK ``source`` (legacy). Once
    stamped, a chunk carries ``source="dip"`` and is never re-selected, so a
    re-run of ``--apply`` reports 0 additional stamps.

Safety (T-11-16):
  * Dry-run is the DEFAULT — it prints a sample of ``xml_rede_id → agenda →
    speech_key`` mappings + counts and mutates NOTHING.
  * ``--apply`` guards every write; it refuses to touch a non-``_dev`` collection
    unless ``--allow-prod`` is passed explicitly (local-only milestone, CLAUDE.md).
  * ``ENV`` / ``QDRANT_URL`` scope the target to ``wahlchat_chunks_{ENV}``.

Usage (local dev):
    cd ai-backend
    # Dry-run (default) — prints sample + counts, no writes:
    QDRANT_URL=http://localhost:6333 ENV=dev \\
        uv run python -m src.ingestion.connectors.bundestag_speeches.migrate_speech_key
    # Apply (mutates the local dev store only):
    QDRANT_URL=http://localhost:6333 ENV=dev \\
        uv run python -m src.ingestion.connectors.bundestag_speeches.migrate_speech_key --apply

Requires (for --apply against the live dev store): make stores-up (Qdrant at
QDRANT_URL) and DIP_API_KEY in ai-backend/.env (the re-parse re-fetches protocol
XML). The dry-run path is safe to run without a DIP key when a resolver is
injected in tests.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from qdrant_client import models

from src.ingestion.connectors.bundestag_speeches.mappers import corpus as corpus_mapper
from src.ingestion.connectors.bundestag_speeches.parser import parse_speeches_from_xml
from src.ingestion.schemas import SourceType
from src.ingestion.setup_collection import COLLECTION_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolvedProtocol:
    """One re-fetched protocol: its ``dokumentnummer`` ("wp/session") + XML text.

    ``dokumentnummer`` is the human "Wahlperiode/Sitzung" form (e.g. ``"20/101"``)
    read from the freshly-fetched protocol document. It is the ONLY reliable
    source of the session number for the shared ``speech_key`` (BL-01): legacy
    chunks stored the internal numeric DIP doc id in ``meta.protocol_id`` (no
    ``"/"``), from which the session cannot be recovered. Either field may be
    ``None`` under A6 graceful degradation (protocol unavailable / dokumentnummer
    absent / XML missing or unparseable).
    """

    dokumentnummer: Optional[str] = None
    xml_text: Optional[str] = None


# A callable that, given a protocol's API id, returns a ResolvedProtocol (or None
# when the protocol is entirely unavailable — A6 graceful fallback). Injectable so
# the dry-run / unit tests never touch the network.
ProtocolResolver = Callable[[str], Optional["ResolvedProtocol"]]

# Backwards-compatible alias (the resolver now yields a ResolvedProtocol, not a
# bare XML string — BL-01). Kept so external references do not break.
ProtocolXmlResolver = ProtocolResolver

_SCROLL_PAGE_SIZE = 256


# =============================================================================
# Data structures
# =============================================================================


@dataclass(frozen=True)
class SpeechInfo:
    """One legacy speech (all chunks of a source_item_id share these fields)."""

    source_item_id: str
    protocol_api_id: Optional[str]
    protocol_id: Optional[str]
    wahlperiode: Optional[int]
    speaker_name: Optional[str]
    xml_rede_id: Optional[str]
    # Full stored meta + citation_title of a representative chunk — used by MED-03
    # to normalise the legacy internal-id representation to the dokumentnummer form
    # via set_payload (all chunks of a speech share these).
    meta_raw: dict = field(default_factory=dict)
    citation_title: Optional[str] = None


@dataclass(frozen=True)
class PlanEntry:
    """A single set_payload the migration would issue for one speech."""

    source_item_id: str
    payload: dict
    speech_key: Optional[str]
    agenda_top_id: Optional[str]
    no_agenda: bool  # True when the agenda could not be recovered (XML gone/absent)


@dataclass
class MigrationPlan:
    """The computed (but not yet applied) migration."""

    entries: list[PlanEntry] = field(default_factory=list)
    # protocol_api_id values whose XML could not be resolved/parsed (A6).
    unresolved_protocols: set[str] = field(default_factory=set)

    @property
    def total_speeches(self) -> int:
        return len(self.entries)

    @property
    def stamped_with_key(self) -> int:
        return sum(1 for e in self.entries if e.speech_key is not None)

    @property
    def no_agenda_count(self) -> int:
        return sum(1 for e in self.entries if e.no_agenda)

    @property
    def unkeyed_count(self) -> int:
        """Speeches that get source='dip' but NO speech_key (wp/session unparseable)."""
        return sum(1 for e in self.entries if e.speech_key is None)


# =============================================================================
# Scroll — enumerate legacy DIP chunks lacking `source`
# =============================================================================


def _legacy_filter() -> models.Filter:
    """Filter: parliamentary_speech chunks that LACK a `source` payload field.

    Legacy DIP chunks were written before the `source` discriminator existed, so
    the field is absent (dropped by exclude_none). New DIP/op chunks carry
    source="dip"/"op" and are excluded — which is what makes the migration
    idempotent (a re-run after --apply selects nothing).
    """
    return models.Filter(
        must=[
            models.FieldCondition(
                key="source_type",
                match=models.MatchValue(value=SourceType.PARLIAMENTARY_SPEECH.value),
            ),
            models.IsEmptyCondition(is_empty=models.PayloadField(key="source")),
        ]
    )


def iter_legacy_speeches(
    qdrant: Any,
    collection_name: str,
    *,
    page_size: int = _SCROLL_PAGE_SIZE,
    limit: Optional[int] = None,
) -> dict[str, SpeechInfo]:
    """Scroll legacy DIP chunks and collapse to one SpeechInfo per source_item_id.

    Multiple chunks (chunk_index 0..N) share a source_item_id; we only need one
    representative per speech because set_payload stamps all chunks of that speech
    at once (via a source_item_id filter).

    Args:
        qdrant:          QdrantClient (or compatible object exposing ``scroll``).
        collection_name: Collection to scroll.
        page_size:       Scroll page size.
        limit:           Stop after collecting this many DISTINCT speeches (smoke test).

    Returns:
        dict source_item_id -> SpeechInfo (insertion-ordered).
    """
    speeches: dict[str, SpeechInfo] = {}
    offset: Any = None
    scroll_filter = _legacy_filter()

    while True:
        points, offset = qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            limit=page_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = getattr(point, "payload", None) or {}
            sid = payload.get("source_item_id")
            if not sid or sid in speeches:
                continue
            meta = payload.get("meta") or {}
            raw_wp = payload.get("wahlperiode")
            try:
                wp = int(raw_wp) if raw_wp is not None else None
            except (TypeError, ValueError):
                wp = None
            speeches[sid] = SpeechInfo(
                source_item_id=str(sid),
                protocol_api_id=(meta.get("protocol_api_id") or None),
                protocol_id=(meta.get("protocol_id") or None),
                wahlperiode=wp,
                speaker_name=(meta.get("speaker_name") or None),
                xml_rede_id=(meta.get("xml_rede_id") or None),
                meta_raw=dict(meta),
                citation_title=(payload.get("citation_title") or None),
            )
            if limit is not None and len(speeches) >= limit:
                return speeches

        if not points or offset is None:
            break

    return speeches


# =============================================================================
# Re-parse — recover xml_rede_id -> agenda_top_id per protocol (no vector recompute)
# =============================================================================


def build_agenda_map(xml_text: Optional[str]) -> Optional[dict[str, Optional[str]]]:
    """Re-parse a protocol XML into ``{xml_rede_id: agenda_top_id}``.

    Uses the SAME defusedxml-guarded ``parse_speeches_from_xml`` as the live
    connector (T-11-17: entity-expansion hardened). Returns None when *xml_text*
    is None (XML unavailable — A6). An empty/malformed XML yields an empty map
    (every rede then falls back to a no-agenda key).
    """
    if xml_text is None:
        return None
    agenda_map: dict[str, Optional[str]] = {}
    for speech in parse_speeches_from_xml(xml_text):
        rede_id = speech.get("xml_rede_id")
        if rede_id:
            agenda_map[str(rede_id)] = speech.get("agenda_top_id")
    return agenda_map


def _compute_key(
    info: SpeechInfo,
    agenda_top_id: Optional[str],
    protocol_id: Optional[str],
) -> Optional[str]:
    """Compute the shared speech_key via the SAME helper the live connector uses.

    Building a row dict and delegating to ``corpus_mapper.compute_speech_key``
    guarantees the migration produces a byte-identical key to the live DIP
    connector for the same speech (parity — the whole point of the shared helper).

    ``protocol_id`` MUST be the recovered "wp/session" dokumentnummer (e.g.
    ``"20/101"``), NOT the stored legacy ``meta.protocol_id`` — which on real
    legacy chunks is the internal numeric DIP doc id (no ``"/"``) and yields
    ``speech_key=None`` (BL-01). ``build_plan`` recovers it from the freshly
    re-fetched protocol document's ``dokumentnummer``.
    """
    row = {
        "wahlperiode": info.wahlperiode,
        "protocol_id": protocol_id,
        "speaker_name": info.speaker_name,
        "agenda_top_id": agenda_top_id,
    }
    return corpus_mapper.compute_speech_key(row)


# =============================================================================
# Plan — compute (without applying) every set_payload
# =============================================================================


def build_plan(
    qdrant: Any,
    collection_name: str,
    resolve_protocol: ProtocolResolver,
    *,
    limit: Optional[int] = None,
) -> MigrationPlan:
    """Compute the migration plan: for each legacy speech, its speech_key + payload.

    Re-fetches + re-parses each distinct protocol exactly once (cached), recovers
    each rede's agenda AND the protocol's ``dokumentnummer`` ("wp/session"), and
    computes the parity-correct speech_key. No writes are performed.

    Args:
        qdrant:            QdrantClient (or compatible).
        collection_name:   Collection to migrate.
        resolve_protocol:  Callable protocol_api_id -> ResolvedProtocol (or None).
        limit:             Cap distinct speeches processed (smoke test).

    Returns:
        A MigrationPlan (entries + unresolved-protocol set).
    """
    speeches = iter_legacy_speeches(qdrant, collection_name, limit=limit)

    # Group by protocol so we re-fetch + re-parse each protocol only once. Cache
    # BOTH the recovered dokumentnummer (for the session component — BL-01) and
    # the agenda map keyed by proto_key.
    proto_cache: dict[
        str, tuple[Optional[str], Optional[dict[str, Optional[str]]]]
    ] = {}
    plan = MigrationPlan()

    for info in speeches.values():
        proto_key = info.protocol_api_id
        if proto_key is None:
            # No API id to re-fetch by → cannot recover agenda (A6). No-agenda key.
            dokumentnummer: Optional[str] = None
            agenda_map: Optional[dict[str, Optional[str]]] = None
        else:
            if proto_key not in proto_cache:
                try:
                    resolved = resolve_protocol(proto_key)
                except Exception as exc:  # noqa: BLE001 — network/parse failure → A6 fallback
                    logger.warning(
                        "migrate: protocol %s resolve failed (%s) — no-agenda fallback",
                        proto_key,
                        exc,
                    )
                    resolved = None
                doknr = resolved.dokumentnummer if resolved else None
                agenda = build_agenda_map(resolved.xml_text if resolved else None)
                proto_cache[proto_key] = (doknr, agenda)
                if agenda is None:
                    plan.unresolved_protocols.add(proto_key)
            dokumentnummer, agenda_map = proto_cache[proto_key]

        if agenda_map is None:
            agenda_top_id = None
            no_agenda = True
        else:
            agenda_top_id = (
                agenda_map.get(info.xml_rede_id) if info.xml_rede_id else None
            )
            no_agenda = agenda_top_id is None

        # BL-01: recover the "wp/session" form for the session component. Prefer
        # the freshly-fetched dokumentnummer; fall back to the stored legacy
        # protocol_id ONLY when it already carries a "/" (already-normalised
        # data). A bare internal id (no "/") yields speech_key=None as before.
        stored_pid = info.protocol_id or ""
        protocol_id_for_key = dokumentnummer or (
            stored_pid if "/" in stored_pid else None
        )

        speech_key = _compute_key(info, agenda_top_id, protocol_id_for_key)
        if speech_key is None:
            logger.warning(
                "migrate: speech %s has unparseable wahlperiode/session "
                "(wp=%r protocol_id=%r) — stamping source='dip' only, no speech_key",
                info.source_item_id,
                info.wahlperiode,
                info.protocol_id,
            )

        payload: dict = {"source": corpus_mapper._DIP_SOURCE}
        if speech_key is not None:
            payload["speech_key"] = speech_key

        # MED-03: normalise the legacy internal-id representation of
        # meta.protocol_id + citation_title to the dokumentnummer "wp/session"
        # form so the corpus is CONSISTENT with newly-ingested chunks (which now
        # store "20/101"). set_payload only — NO vector recompute, NO vector write.
        # Only when the freshly-fetched dokumentnummer differs from the stored
        # (internal-id) value; a chunk already carrying the dokumentnummer is left
        # untouched, keeping the migration idempotent on these fields too.
        if dokumentnummer and (info.protocol_id or "") != dokumentnummer:
            if info.meta_raw:
                payload["meta"] = {**info.meta_raw, "protocol_id": dokumentnummer}
            old_frag = f"(Protokoll {info.protocol_id})"
            if info.citation_title and old_frag in info.citation_title:
                payload["citation_title"] = info.citation_title.replace(
                    old_frag, f"(Protokoll {dokumentnummer})"
                )

        plan.entries.append(
            PlanEntry(
                source_item_id=info.source_item_id,
                payload=payload,
                speech_key=speech_key,
                agenda_top_id=agenda_top_id,
                no_agenda=no_agenda,
            )
        )

    return plan


# =============================================================================
# Apply — stamp payloads via set_payload (NO vector recompute, NO vector write)
# =============================================================================


def apply_plan(qdrant: Any, collection_name: str, plan: MigrationPlan) -> int:
    """Issue one ``set_payload`` per speech (stamps all its chunks). No vectors.

    Uses a source_item_id filter so every chunk of the speech is stamped in a
    single call. Returns the number of set_payload calls issued.
    """
    for entry in plan.entries:
        qdrant.set_payload(
            collection_name=collection_name,
            payload=entry.payload,
            points=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="source_item_id",
                            match=models.MatchValue(value=entry.source_item_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
    return len(plan.entries)


# =============================================================================
# Orchestration — dry-run print / apply
# =============================================================================


def run_migration(
    qdrant: Any,
    collection_name: str,
    resolve_protocol: ProtocolResolver,
    *,
    apply: bool = False,
    limit: Optional[int] = None,
    sample: int = 5,
    out=sys.stdout,
) -> MigrationPlan:
    """Compute the plan, print a sample + counts, and (only if apply) stamp payloads.

    Args:
        qdrant:            QdrantClient (or compatible).
        collection_name:   Target collection.
        resolve_protocol:  Callable protocol_api_id -> ResolvedProtocol (or None).
        apply:             When True, perform the set_payload writes. Default
                           False (dry-run: prints, mutates nothing).
        limit:             Cap distinct speeches processed (smoke test).
        sample:            Number of xml_rede_id→agenda→key rows to print.
        out:               Stream for human-facing output.

    Returns:
        The computed MigrationPlan (already applied when apply=True).
    """
    plan = build_plan(qdrant, collection_name, resolve_protocol, limit=limit)

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"[{mode}] collection={collection_name}", file=out)
    print(f"  legacy speeches (distinct source_item_id): {plan.total_speeches}", file=out)
    print(f"  → would stamp speech_key: {plan.stamped_with_key}", file=out)
    print(f"  → no-agenda fallback:     {plan.no_agenda_count}", file=out)
    print(f"  → source-only (no key):   {plan.unkeyed_count}", file=out)
    print(f"  → unresolved protocols:   {len(plan.unresolved_protocols)}", file=out)

    print(f"\n  sample (first {sample}) xml_rede_id → agenda → speech_key:", file=out)
    for entry in plan.entries[:sample]:
        print(
            f"    sid={entry.source_item_id}  agenda_top_id={entry.agenda_top_id!r}"
            f"  speech_key={entry.speech_key!r}",
            file=out,
        )

    if not apply:
        print("\n  DRY-RUN — no writes performed. Re-run with --apply to stamp.", file=out)
        return plan

    stamped = apply_plan(qdrant, collection_name, plan)
    print(f"\n  APPLIED — issued {stamped} set_payload call(s) (0 OpenAI tokens).", file=out)
    return plan


# =============================================================================
# Default DIP-backed protocol XML resolver (production path)
# =============================================================================


def make_dip_resolver() -> ProtocolResolver:
    """Build the production resolver: DIP protocol lookup → dokumentnummer + XML.

    Lazily constructs a DipClient (requires DIP_API_KEY). Caches nothing itself —
    build_plan caches per protocol. Returns a ResolvedProtocol carrying the
    protocol's ``dokumentnummer`` ("wp/session" — the ONLY reliable session source
    for the shared speech_key, BL-01) and its XML text. Any lookup/fetch failure
    degrades gracefully: a missing dokumentnummer or XML becomes ``None`` in the
    returned struct (A6) rather than aborting the migration; a total lookup
    failure returns ``None``.
    """
    from src.ingestion.connectors.bundestag_speeches.client import (  # noqa: PLC0415
        fetch_text,
    )
    from src.ingestion.connectors.bundestag_speeches.connector import (  # noqa: PLC0415
        _require_dip_key,
    )
    from src.ingestion.connectors.bundestag_speeches.client import DipClient  # noqa: PLC0415

    client = DipClient(api_key=_require_dip_key())

    def _resolve(protocol_api_id: str) -> Optional[ResolvedProtocol]:
        try:
            doc = client.get(f"/plenarprotokoll/{protocol_api_id}")
        except Exception as exc:  # noqa: BLE001 — A6 fallback
            logger.warning(
                "migrate: DIP protocol lookup failed for %s (%s)", protocol_api_id, exc
            )
            return None
        dokumentnummer = str(doc.get("dokumentnummer") or "").strip() or None
        xml_url = (doc.get("fundstelle") or {}).get("xml_url") or ""
        if not xml_url:
            logger.warning("migrate: protocol %s has no xml_url — no-agenda", protocol_api_id)
            return ResolvedProtocol(dokumentnummer=dokumentnummer, xml_text=None)
        try:
            xml_text: Optional[str] = fetch_text(xml_url)
        except Exception as exc:  # noqa: BLE001 — A6 fallback
            logger.warning(
                "migrate: protocol %s XML fetch failed (%s)", protocol_api_id, exc
            )
            xml_text = None
        return ResolvedProtocol(dokumentnummer=dokumentnummer, xml_text=xml_text)

    return _resolve


# =============================================================================
# __main__ entrypoint
# =============================================================================


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "One-off migration: stamp speech_key + source='dip' onto legacy DIP "
            "parliamentary_speech chunks by re-parsing protocol XML (no vector recompute). "
            "Dry-run by default; --apply mutates the local dev store only."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform the set_payload writes (default: dry-run, no writes).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N distinct speeches (smoke test).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=5,
        metavar="N",
        help="Print N xml_rede_id→agenda→speech_key sample rows (default 5).",
    )
    parser.add_argument(
        "--allow-prod",
        action="store_true",
        help=(
            "Permit --apply against a non-'_dev' collection. Refused by default "
            "(local-only milestone, CLAUDE.md; T-11-16)."
        ),
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    # Load ai-backend/.env if present (DIP_API_KEY / QDRANT_URL).
    # migrate_speech_key.py sits at:
    #   ai-backend/src/ingestion/connectors/bundestag_speeches/migrate_speech_key.py
    # parents[4] = ai-backend/
    from dotenv import load_dotenv  # noqa: PLC0415

    _env_path = Path(__file__).resolve().parents[4] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = _build_arg_parser().parse_args(argv)

    # Safety guard (T-11-16): never --apply to a non-dev collection unless forced.
    if args.apply and not COLLECTION_NAME.endswith("_dev") and not args.allow_prod:
        print(
            f"REFUSING --apply on non-dev collection {COLLECTION_NAME!r}. "
            "This migration is local-dev-only (CLAUDE.md). "
            "Set ENV=dev, or pass --allow-prod to override.",
            file=sys.stderr,
        )
        return 2

    from qdrant_client import QdrantClient  # noqa: PLC0415

    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant = QdrantClient(url=qdrant_url, api_key=os.getenv("QDRANT_API_KEY"))

    resolve = make_dip_resolver()

    run_migration(
        qdrant,
        COLLECTION_NAME,
        resolve,
        apply=args.apply,
        limit=args.limit,
        sample=args.sample,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
