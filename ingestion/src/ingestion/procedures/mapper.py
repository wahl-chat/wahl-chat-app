# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""DIP Vorgang + Vorgangspositionen → ProcedureRecord → profile chunk."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any, Optional

from ingestion.ids import compute_source_item_id, make_chunk_key
from ingestion.party_slugs import CANONICAL_PARTY_SLUGS, normalize_party_label
from ingestion.procedures.scope import kind_of
from ingestion.schemas import AuthorityTier, ChunkRecord, ProcedureLink, SourceType
from wahlchat_common.procedures import (
    DrucksacheRef,
    ProcedureRecord,
    ProcedureStage,
    StageDecision,
    milestones,
)

# A chunk that belongs to no single party (same sentinel as votes).
NO_PARTY = "_all"

_DIP_VORGANG_URL = "https://dip.bundestag.de/vorgang/{id}"
_GROUP_PREFIX = re.compile(r"^(fraktion|gruppe)\s+(der\s+)?", re.IGNORECASE)
_MAX_DESKRIPTOREN_IN_TEXT = 30


def party_ids_of(urheber: list[str]) -> list[str]:
    """Slugs of the Fraktionen/Gruppen among DIP urheber or initiative labels.

    'Fraktion der CDU/CSU' → 'cdu', 'Gruppe Die Linke' → 'linke'. The
    Bundesregierung, Länder and committees are no party and are skipped.
    """
    slugs: set[str] = set()
    for label in urheber:
        if not _GROUP_PREFIX.match(label.strip()):
            continue
        name = normalize_party_label(_GROUP_PREFIX.sub("", label.strip()))
        slug = CANONICAL_PARTY_SLUGS.get(name)
        if slug:
            slugs.add(slug)
    return sorted(slugs)


def _day(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _decision(raw: dict[str, Any]) -> StageDecision:
    numbers = raw.get("dokumentnummer") or ""
    return StageDecision(
        tenor=raw.get("beschlusstenor") or "",
        vote_kind=raw.get("abstimmungsart"),
        result=(raw.get("abstimm_ergebnis_bemerkung") or "").strip() or None,
        majority=raw.get("mehrheit"),
        document_numbers=[n.strip() for n in numbers.split(",") if n.strip()],
        page=raw.get("seite"),
    )


def _page(fundstelle: dict[str, Any]) -> Optional[str]:
    start = fundstelle.get("anfangsseite")
    if start is None:
        return None
    return f"{start}{fundstelle.get('anfangsquadrant') or ''}"


def stage_from_position(position: dict[str, Any]) -> Optional[ProcedureStage]:
    """None for a position without a usable date (DIP data error)."""
    day = _day(position.get("datum"))
    if day is None:
        return None
    fundstelle = position.get("fundstelle") or {}
    kind = fundstelle.get("dokumentart")
    return ProcedureStage(
        position_id=str(position["id"]),
        date=day,
        chamber=position.get("zuordnung") or "BT",
        name=position.get("vorgangsposition") or "",
        document_kind=kind if kind in ("Drucksache", "Plenarprotokoll") else None,
        document_number=fundstelle.get("dokumentnummer"),
        page=_page(fundstelle),
        url=fundstelle.get("pdf_url"),
        decisions=[_decision(d) for d in position.get("beschlussfassung") or []],
    )


def drucksachen_from_positions(positions: list[dict[str, Any]]) -> list[DrucksacheRef]:
    """One ref per (chamber, number), in date order."""
    refs: dict[tuple[str, str], DrucksacheRef] = {}
    for position in sorted(
        positions, key=lambda p: (p.get("datum") or "", str(p["id"]))
    ):
        fundstelle = position.get("fundstelle") or {}
        if fundstelle.get("dokumentart") != "Drucksache" or not fundstelle.get(
            "dokumentnummer"
        ):
            continue
        chamber = fundstelle.get("herausgeber") or position.get("zuordnung") or "BT"
        key = (chamber, fundstelle["dokumentnummer"])
        if key in refs:
            continue
        urheber = [str(u) for u in fundstelle.get("urheber") or []]
        refs[key] = DrucksacheRef(
            number=fundstelle["dokumentnummer"],
            chamber=chamber,
            doc_type=fundstelle.get("drucksachetyp"),
            date=_day(fundstelle.get("datum")),
            urheber=urheber,
            party_ids=party_ids_of(urheber),
            pdf_url=fundstelle.get("pdf_url"),
        )
    return list(refs.values())


def _record_hash(record: ProcedureRecord) -> str:
    """Hash of everything stored except bookkeeping that changes on its own."""
    stored = record.model_dump(
        mode="json",
        exclude={"content_hash", "has_links", "stage_changed_on", "dip_updated_at"},
    )
    return hashlib.sha256(
        json.dumps(stored, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def build_record(
    vorgang: dict[str, Any],
    positions: list[dict[str, Any]],
    *,
    previous: Optional[ProcedureRecord],
    today: date,
) -> ProcedureRecord:
    """Map one DIP Vorgang and its stages.

    ``stage_changed_on`` moves to ``today`` only when a dated stage appears
    that the previous record did not have. On first sight it is the newest
    stage's date, so a backfill does not mark every procedure as just moved.
    """
    stages = sorted(
        (s for s in (stage_from_position(p) for p in positions) if s is not None),
        key=lambda s: (s.date, s.position_id),
    )
    latest = stages[-1] if stages else None
    initiative = [str(i) for i in vorgang.get("initiative") or []]
    drucksachen = drucksachen_from_positions(positions)
    vid = str(vorgang["id"])

    if previous is None:
        stage_changed_on = latest.date if latest else None
    else:
        known = {s.position_id for s in previous.stages}
        is_new = any(s.position_id not in known for s in stages)
        stage_changed_on = today if is_new else previous.stage_changed_on

    record = ProcedureRecord(
        vorgang_id=vid,
        wahlperiode=int(vorgang["wahlperiode"]),
        vorgangstyp=vorgang.get("vorgangstyp") or "",
        kind=kind_of(vorgang.get("vorgangstyp") or ""),
        titel=(vorgang.get("titel") or "").strip(),
        abstract=(vorgang.get("abstract") or "").strip() or None,
        beratungsstand=vorgang.get("beratungsstand"),
        initiative=initiative,
        initiative_party_ids=party_ids_of(initiative),
        sachgebiete=sorted(set(vorgang.get("sachgebiet") or [])),
        deskriptoren=[
            d["name"] for d in vorgang.get("deskriptor") or [] if d.get("name")
        ],
        gesta=vorgang.get("gesta"),
        started_on=_day(vorgang.get("datum")) or (stages[0].date if stages else None),
        stages=stages,
        drucksachen=drucksachen,
        drucksache_numbers=sorted({d.number for d in drucksachen if d.chamber == "BT"}),
        latest_stage=latest.name if latest else None,
        latest_stage_on=latest.date if latest else None,
        stage_changed_on=stage_changed_on,
        has_links=previous.has_links if previous else False,
        dip_url=_DIP_VORGANG_URL.format(id=vid),
        dip_updated_at=vorgang.get("aktualisiert") or "",
        content_hash="",
    )
    return record.model_copy(update={"content_hash": _record_hash(record)})


def profile_text(record: ProcedureRecord) -> str:
    """What a search for the procedure should match: names, topics, course."""
    lines = [
        f"Vorgang: {record.titel}",
        f"Typ: {record.vorgangstyp} ({record.wahlperiode}. Wahlperiode)",
    ]
    if record.initiative:
        lines.append(f"Initiative: {', '.join(record.initiative)}")
    if record.beratungsstand:
        lines.append(f"Stand: {record.beratungsstand}")
    if record.sachgebiete:
        lines.append(f"Sachgebiete: {', '.join(record.sachgebiete)}")
    if record.deskriptoren:
        terms = record.deskriptoren[:_MAX_DESKRIPTOREN_IN_TEXT]
        lines.append(f"Schlagworte: {', '.join(terms)}")
    if record.abstract:
        lines.append(f"Inhalt: {record.abstract}")
    course = milestones(record.stages)
    if course:
        lines.append("Verlauf:")
        lines.extend(f"- {m.date.isoformat()} {m.chamber}: {m.name}" for m in course)
    return "\n".join(lines)


def profile_chunk(record: ProcedureRecord, *, today: date) -> ChunkRecord:
    """One vector per procedure; the timeline itself lives in Firestore."""
    source_item_id = compute_source_item_id(
        SourceType.PROCEDURE.value, record.vorgang_id
    )
    text = profile_text(record)
    parties = record.initiative_party_ids
    publish_date = record.latest_stage_on or record.started_on or today
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "text": text,
                "parties": parties,
                "publish_date": publish_date.isoformat(),
                "sachgebiete": record.sachgebiete,
                "wahlperiode": record.wahlperiode,
                "citation": [record.dip_url, record.titel],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return ChunkRecord(
        chunk_key=make_chunk_key(source_item_id, 0),
        source_item_id=source_item_id,
        chunk_index=0,
        text=text,
        party_id=parties[0] if len(parties) == 1 else NO_PARTY,
        party_ids=parties or None,
        region="DE",
        authority_tier=AuthorityTier.FACTUAL_RECORD,
        source_type=SourceType.PROCEDURE,
        publish_date=publish_date,
        citation_url=record.dip_url,
        citation_title=f"Vorgang: {record.titel}",
        wahlperiode=record.wahlperiode,
        source_parent_key=f"{SourceType.PROCEDURE.value}:{record.vorgang_id}",
        content_hash=content_hash,
        vorgang_ids=[record.vorgang_id],
        sachgebiete=record.sachgebiete or None,
        # The checked_on date is not hashed, so a re-sync with no change
        # keeps the stored point as it is.
        procedure_link=ProcedureLink(method="source", checked_on=today),
    )
