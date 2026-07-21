# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""openparliament.tv speech connector package — video-timestamped plenary speeches.

Source: the OpenParliamentTV-Data-DE GitHub repository's `processed/*-session.json`
bulk files (keyless). These carry sentence-level, video-aligned German Bundestag
speech transcripts. This connector layer *coexists* with the DIP bundestag_speeches
connector, deduping downstream on `speech_key` and adding a timed `sentence_map`
plus a video deep-link payload.

Package structure (mirrors connectors/bundestag_speeches/):
  connector.py        — OpenParliamentTvConnector(BaseConnector): discover/fetch/normalize
  client.py           — OpTvClient: keyless GitHub-bulk enumerate + pinned-host raw fetch, curl fallback
  parser.py           — parse_session_json: session JSON → speech dicts w/ alignment gate + sentence_map
  schemas.py          — OpSpeechMeta (Pydantic, extra="forbid"): video/audio/timestamp payload
  constants.py        — RAW_BASE, TREES_URL, SESSION_FILE_RE, LOOKBACK_DAYS, _OP_FACTION_SLUG_MAP
  mappers/
    corpus.py         — build_chunk_records, op_party_slug
"""
