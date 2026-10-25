# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pure transform mappers for the Abgeordnetenwatch connector.

All functions in this sub-package are I/O-free (no network, no Firestore, no
filesystem reads) and deterministic — suitable for unit testing without mocks.

Modules:
  stance.py  — aggregate_fraction_tallies(votes) -> dict[int, FractionTally]
               derive_stance(yes, no, abstain, no_show) -> Stance
               fraction_to_party_slug(fraction_id, fraction_map) -> str
  corpus.py  — chunk_poll(source_item, raw) -> list[ChunkRecord]
"""
