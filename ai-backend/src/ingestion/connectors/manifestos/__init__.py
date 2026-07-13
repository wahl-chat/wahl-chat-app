# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Manifesto connector package — party Wahlprogramme → party_manifesto corpus.

Source: the Abgeordnetenwatch ``election-program`` API (reuses the shared
``AWClient`` from the abgeordnetenwatch connector package).

Single-store shape: produces ChunkRecord list directly from
normalize() — embed + upsert are owned by the runner (run.py).

Citations point at the original source URL (the AW ``file`` PDF URL or the link
URI) — wahl.chat does not store or re-serve the files, so there is no local PDF
storage and no Firestore source-doc.

Package structure (mirrors connectors/abgeordnetenwatch/):
  connector.py        — ManifestoConnector(BaseConnector): discover/fetch/normalize
                        + shared I/O helpers (_fetch_period_date, load_program_pages)
  bulk.py             — standalone bulk CLI: the ingest() loop with --dry-run /
                        --ids / --limit flags.
                        Runs via `python -m src.ingestion.connectors.manifestos.bulk`.
  mappers/
    corpus.py         — pure transforms (slug/region/wahlperiode/chunk/build,
                        plus trafilatura main-content extraction), no I/O

Two entrypoints, one data path:
  - The generic runner (run.py --connector manifestos) drives the BaseConnector
    interface (Qdrant-cursor embed path).
  - bulk.py is the bespoke local-dev workflow (--dry-run / --ids / --limit).
  Both share connector.py's I/O helpers and mappers/corpus.py's transforms.
"""
