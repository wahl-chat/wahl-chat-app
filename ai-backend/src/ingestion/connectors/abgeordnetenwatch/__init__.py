# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Abgeordnetenwatch connector package.

Single-store shape: produces ChunkRecord list directly from normalize() —
no Firestore, no GCS, no matcher dual-write.

Package structure:
  client.py           — AW v2 API session + fixed-delay pacing
  connector.py        — AbgeordnetenwatchVotesConnector(BaseConnector)
  mappers/            — pure transforms (no I/O)
    stance.py         — tally -> stance + fraction -> party
    corpus.py         — poll -> vote_record ChunkRecord list

The party_manifesto corpus is produced by the separate manifestos connector
package (connectors/manifestos/) — this package produces vote_record only.
"""
