# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

import json
from pathlib import Path

from src.daily_digest.models import DailyDigest

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "firebase"
    / "firestore_data"
    / "emulator"
    / "daily_digests.json"
)


def test_emulator_sample_digests_match_the_stored_shape() -> None:
    # `make seed-local` writes these into the emulator for the feed; they must
    # stay what the builder would write, or local review shows a fake feed.
    digests = [DailyDigest.model_validate(d) for d in json.loads(FIXTURE.read_text())]
    assert digests
    for digest in digests:
        assert digest.session is not None
        assert all(s.opening_quote for s in digest.session.sections)
