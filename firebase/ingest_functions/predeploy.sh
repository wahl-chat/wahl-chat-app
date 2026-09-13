#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
#
# Firebase predeploy for the "ingest" codebase (wired in firebase.json):
# build the ingestion package AND its workspace dependency wahlchat-common
# into vendor/ so requirements.txt can install them — pip cannot resolve a
# workspace member from PyPI.
set -euo pipefail
cd "$(dirname "$0")"

rm -rf vendor
(
  cd ../..
  uv build --package ingestion --wheel --out-dir firebase/ingest_functions/vendor
  uv build --package wahlchat-common --wheel --out-dir firebase/ingest_functions/vendor
)

# The wheel filenames are pinned in requirements.txt; a version bump in either
# pyproject.toml must be mirrored there — fail the deploy, not the cloud build,
# when they disagree.
for wheel_path in vendor/*.whl; do
  wheel=$(basename "$wheel_path")
  grep -q "vendor/${wheel}" requirements.txt || {
    echo "ERROR: built ${wheel} but requirements.txt pins a different wheel filename." >&2
    exit 1
  }
done

echo "predeploy: bundled $(ls vendor | tr '\n' ' ')"
