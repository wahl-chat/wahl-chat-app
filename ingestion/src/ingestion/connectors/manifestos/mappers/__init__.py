# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pure (no-I/O) transforms for the manifesto connector.

corpus.py — election-program record → party_manifesto ChunkRecord list, plus the
            slug/region/wahlperiode derivation and token-bounded page chunking.
"""
