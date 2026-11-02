# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""The parliament feed: per parliament and sitting day, every debate and vote
becomes one feed item, derived from the corpus once and reused by every
surface that shows it (Firestore ``feed_items``, grouped by ``feed_editions``,
found through the Qdrant feed collection)."""
