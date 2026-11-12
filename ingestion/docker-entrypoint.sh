#!/bin/sh
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
#
# Bootstrap-then-run for the scheduled ingestion Job. The connector itself is
# selected by CONNECTOR_ID in the job spec, which run.py reads directly, so no
# container-command override is needed.
set -eu

# Ensure the collection + payload indexes exist before ingesting. Idempotent
# and existence-guarded, so a snapshot-recovered collection is left intact;
# this is what stops the runner's first get_cursor() from 404ing on a fresh
# store (no separate bootstrap step to remember before a scheduled Job runs).
python -m ingestion.setup_collection

# The parliament feed is not a registry connector (it builds from the corpus
# rather than filling it), so CONNECTOR_ID=feed hands over to its own runner,
# after creating its search collection the same idempotent way.
if [ "${CONNECTOR_ID:-}" = "feed" ]; then
    python -m ingestion.feed.index
    exec python -m ingestion.feed.bulk "$@"
fi

# Extra runner flags (e.g. --batch-size, --time-budget) may be passed as
# container args; forward them.
exec python -m ingestion.run "$@"
