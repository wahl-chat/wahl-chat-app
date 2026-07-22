# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""parse_speeches_from_xml — XML→speech-dict transform, hardened via defusedxml.

Security: uses defusedxml.ElementTree to block billion-laughs /
entity-expansion attacks on remote protocol XML.

Public API:
  parse_speeches_from_xml(xml_text: str) -> list[dict]
    Extracts speaker/party/text dicts from a plenary protocol XML string.
    Skips <kommentar> nodes; applies merged-name visible-label override.
"""

from __future__ import annotations

import re

import defusedxml.ElementTree as ElementTree  # blocks entity-expansion / billion-laughs

from .utils import is_known_party, normalize_party, normalize_whitespace


def parse_visible_speaker_label(tail: str | None) -> dict:
    tail = normalize_whitespace(tail)
    if not tail:
        return {}

    match = re.match(r"^(?P<name>.+?)\s*\((?P<party>[^()]*)\)$", tail.rstrip(":"))
    if not match:
        return {}

    party = normalize_party(match.group("party"))
    if not is_known_party(party):
        return {}

    return {
        "speaker_name": normalize_whitespace(match.group("name")),
        "party": party,
    }


def has_merged_name(value: str | None) -> bool:
    value = normalize_whitespace(value)
    return bool(value and re.search(r"[a-zäöüß][A-ZÄÖÜ]", value))


def has_suspicious_speaker_metadata(speaker: dict) -> bool:
    return not is_known_party(speaker.get("party")) or has_merged_name(
        speaker.get("speaker_name")
    )


def parse_speaker(redner) -> dict:  # type: ignore[return]
    name = redner.find("name")
    if name is None:
        return {}

    title = normalize_whitespace(
        " ".join(node.text or "" for node in name.findall("titel"))
    )
    first_name = normalize_whitespace(
        " ".join(node.text or "" for node in name.findall("vorname"))
    )
    last_name = normalize_whitespace(
        " ".join(node.text or "" for node in name.findall("nachname"))
    )
    party = normalize_whitespace(name.findtext("fraktion"))

    speaker: dict = {
        "speaker_xml_id": redner.get("id"),
        "speaker_name": " ".join(
            part for part in [title, first_name, last_name] if part
        ),
        "party": party,
    }

    # Some official XML records have merged structured metadata, while the visible label is correct.
    visible_speaker = parse_visible_speaker_label(redner.tail)
    if visible_speaker and has_suspicious_speaker_metadata(speaker):
        speaker.update(visible_speaker)

    return speaker


def paragraph_text(paragraph) -> str:
    parts = []
    if paragraph.text:
        parts.append(paragraph.text)

    for child in paragraph:
        if child.tag != "kommentar":
            parts.append(" ".join(child.itertext()))
        if child.tail:
            parts.append(child.tail)

    return normalize_whitespace(" ".join(parts)) or ""


def parse_speeches_from_xml(xml_text: str) -> list[dict]:
    """Parse a plenary protocol XML string into a list of speech dicts.

    Each dict contains: xml_rede_id, speaker_xml_id, speaker_name, party, text,
    agenda_top_id.
    Skips <kommentar> nodes (applause, interjections).
    Applies merged-name visible-label override (parse_speaker).

    agenda_top_id is the ``top-id`` of the enclosing <tagesordnungspunkt> for
    each <rede> (e.g. "20"), or None when a rede has no enclosing agenda item
    (graceful no-agenda fallback). ElementTree exposes no parent pointers,
    so the enclosing agenda is resolved by walking each <tagesordnungspunkt> and
    recording a rede_id → top_id map before the main <rede> loop.

    Raises defusedxml.EntitiesForbidden on entity-expansion attacks.
    Returns [] on malformed XML (ParseError is NOT caught here — callers
    that need graceful degradation should catch ElementTree.ParseError).
    """
    try:
        root = ElementTree.fromstring(xml_text.encode("utf-8"))
    except ElementTree.ParseError:
        return []

    # Map each <rede> id to the top-id of its enclosing <tagesordnungspunkt>.
    # ElementTree has no parent pointers, so iterate the agenda items and their
    # descendant <rede> nodes to build the lookup. A rede with no enclosing
    # tagesordnungspunkt is simply absent from the map → agenda_top_id None.
    agenda_top_id_by_rede: dict[str, str] = {}
    for agenda_node in root.findall(".//tagesordnungspunkt"):
        top_id = agenda_node.get("top-id")
        if not top_id:
            continue
        for rede_node in agenda_node.findall(".//rede"):
            rede_id = rede_node.get("id")
            if rede_id is not None:
                agenda_top_id_by_rede.setdefault(rede_id, top_id)

    speeches: list[dict] = []

    for speech_node in root.findall(".//rede"):
        speaker_node = speech_node.find("./p[@klasse='redner']/redner")
        speaker = parse_speaker(speaker_node) if speaker_node is not None else {}
        speaker_id = speaker.get("speaker_xml_id")
        collect_text = bool(speaker_id)

        paragraphs: list[str] = []
        for child in list(speech_node):
            if child.tag == "p" and child.get("klasse") == "redner":
                redner = child.find("redner")
                current_speaker_id = redner.get("id") if redner is not None else None
                collect_text = bool(speaker_id) and current_speaker_id == speaker_id
                continue

            if child.tag == "name":
                collect_text = False
                continue

            if child.tag == "kommentar":
                continue

            if child.tag != "p" or not collect_text:
                continue

            text = paragraph_text(child)
            if text:
                paragraphs.append(text)

        rede_id = speech_node.get("id")
        speeches.append(
            {
                "xml_rede_id": rede_id,
                "text": "\n".join(paragraphs).strip() or None,
                "agenda_top_id": agenda_top_id_by_rede.get(rede_id)
                if rede_id is not None
                else None,
                **speaker,
            }
        )

    return speeches
