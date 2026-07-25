# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Bundestag speeches connector package — plenary protocol speeches → parliamentary_speech corpus.

Source: DIP Bundestag API (search.dip.bundestag.de) for protocol discovery and
XML download of individual plenary protocol transcripts.

Live incremental connector: produces ChunkRecord list
directly from normalize() — embed + upsert are owned by the runner (run.py).

Package structure (mirrors connectors/abgeordnetenwatch/):
  connector.py        — BundestagSpeechesConnector(BaseConnector): discover/fetch/normalize
  client.py           — DipClient: paginated HTTP, curl challenge fallback
  parser.py           — parse_speeches_from_xml (hardened via defusedxml)
  mdb.py              — load_mdb_lookup, mdb_party_for_speech, mdb_record_for_speaker_name
  constants.py        — BASE_URL, PARTY_ALIASES, VALID_PARTIES, MDB_STAMMDATEN_FILE
  utils.py            — normalize_party, normalize_whitespace
  bulk.py             — optional --from-jsonl backfill (manifestos bulk.py analog)
  mappers/
    corpus.py         — build_chunk_records, chunk_text, party_to_slug
"""
