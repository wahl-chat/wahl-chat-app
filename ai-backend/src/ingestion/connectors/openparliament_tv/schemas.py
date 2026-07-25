# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Source-owned metadata model for the openparliament_tv connector.

`OpSpeechMeta` holds the video/audio/timestamp payload that is specific to op
speeches (the sentence-level timed map + media deep-link URIs + Bundestag/ODbL
attribution). It is dumped into `ChunkRecord.meta` via
``model_dump(mode="json", exclude_none=True)`` by the corpus mapper, so
absent fields never reach Qdrant as NULLs.

Design mirrors ingestion.schemas.SpeechMeta:
  - ``model_config = ConfigDict(frozen=True, extra="forbid")`` — an unexpected key
    raises a ValidationError (input-validation / DoS mitigation: op JSON
    is validated through this model rather than trusted blind).
  - All fields Optional with descriptions; the mapper populates what the source
    provides and lets ``exclude_none=True`` drop the rest.

None of these fields are Qdrant-indexed — they belong in ``meta`` per the envelope
philosophy (indexed filters stay top-level on ChunkRecord; descriptive/source
payload lives in the nested meta object).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OpSpeechMeta(BaseModel):
    """Source-owned nested metadata for openparliament.tv parliamentary_speech chunks.

    Carries the video deep-link payload and the timed sentence map that the
    second-pass citation locator (chat_service.py) uses to build
    ``video_uri#t={ts_start}`` links, plus Bundestag/ODbL attribution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # --- media deep-link payload (stored as strings; NEVER fetched during ingest) ---
    video_uri: Optional[str] = Field(
        None,
        description="Source-supplied video file URI (media.videoFileURI); deep-link base",
    )
    audio_uri: Optional[str] = Field(
        None, description="Source-supplied audio file URI (media.audioFileURI)"
    )
    source_page: Optional[str] = Field(
        None,
        description="Human-facing source page (media.sourcePage, e.g. dbtg.tv/fvid/...)",
    )
    origin_media_id: Optional[str] = Field(
        None,
        description="Bundestag origin media id (media.originMediaID); op's stable speech id",
    )

    # --- agenda context ---
    agenda_item_title: Optional[str] = Field(
        None, description="Human-readable agenda item title (agendaItem.title)"
    )
    agenda_item_official: Optional[str] = Field(
        None,
        description="Official agenda item label (agendaItem.officialTitle, e.g. 'Tagesordnungspunkt 20')",
    )

    # --- speaker identity ---
    speaker_wid: Optional[str] = Field(
        None, description="Wikidata person id of the main speaker (people[].wid)"
    )
    speaker_name: Optional[str] = Field(
        None, description="Full name / label of the main speaker (people[].label)"
    )

    # --- transcript provenance / alignment gate outcome ---
    transcript_type: Optional[str] = Field(
        None, description="Transcript kind on the ingested chunk — always 'proceedings'"
    )
    aligned: Optional[bool] = Field(
        None, description="Video-alignment flag — always True on ingested chunks"
    )

    # --- the timed sentence map (video deep-link source) ---
    sentence_map: Optional[list[dict]] = Field(
        None,
        description=(
            "Flattened, ordered list of {text, ts_start, ts_end} for each main-speaker "
            "sentence; ts values are per-speech-relative seconds cast to float."
        ),
    )

    # --- attribution the app can later render (ODbL / Bundestag) ---
    creator: Optional[str] = Field(
        None, description="Content creator for attribution (e.g. 'Deutscher Bundestag')"
    )
    license: Optional[str] = Field(
        None,
        description="License string for attribution (e.g. Bundestag Nutzungsbedingungen)",
    )
    source_data: Optional[str] = Field(
        None,
        description="Data-source attribution label (e.g. 'openparliament.tv (ODbL)')",
    )

    # --- DIP transcript cross-link (grafted post-upsert, not set at ingest) ---
    transcript_pdf_url: Optional[str] = Field(
        None,
        description=(
            "PDF URL of the official DIP plenary-protocol transcript for the SAME "
            "speech (matched on speech_key). Grafted onto the surviving op record by "
            "supersede_dip_duplicates so one speech source exposes BOTH the video "
            "deep-link and the transcript PDF. None at ingest / when no DIP "
            "counterpart exists."
        ),
    )
