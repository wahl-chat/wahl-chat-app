# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Uploaded-manifesto connector — party PDFs we received directly.

For elections with no Abgeordnetenwatch coverage (upcoming and communal ones),
parties send their Wahlprogramme to us as files. They are uploaded to the public
Storage bucket as ``public/{context_id}/{party_id}/{name}_{YYYY-MM-DD}.pdf`` and
ingested into the same ``party_manifesto`` corpus with ``source="upload"``.

connector.py         — manifest-driven discover/fetch/normalize.
election_fixtures.py — region/level/publish_date/party list from the seed files.
storage_paths.py     — upload-path parsing and bucket-URL construction.
mappers/corpus.py    — pure record building.
"""
