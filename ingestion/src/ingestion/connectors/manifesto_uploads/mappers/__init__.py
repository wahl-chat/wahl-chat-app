# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Pure (no-I/O) transforms for the uploaded-manifesto connector.

corpus.py — upload reference + election fixture → party_manifesto ChunkRecord list,
            with per-chunk ``#page=`` citation anchors and a provenance-covering
            content hash.
"""
