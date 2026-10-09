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
  # The wheels carry version ranges only; pin their dependencies to uv.lock so the
  # function runs the same library versions as the tests and the ingestion jobs.
  uv export --package ingestion --frozen --no-dev --no-hashes --no-emit-workspace \
    --no-header --output-file firebase/ingest_functions/vendor/constraints.txt >/dev/null
)

# The wheel filenames are pinned in requirements.in; a version bump in either
# pyproject.toml must be mirrored there — fail the deploy, not the cloud build,
# when they disagree.
for wheel_path in vendor/*.whl; do
  wheel=$(basename "$wheel_path")
  grep -q "vendor/${wheel}" requirements.in || {
    echo "ERROR: built ${wheel} but requirements.in pins a different wheel filename." >&2
    exit 1
  }
done

# The Cloud Functions build caches the installed dependencies by the content of
# requirements.txt, and neither the wheel filenames nor the constraints path change
# with what they contain. A digest of the wheels' contents (not of the zip files,
# which carry build timestamps) and of the constraints makes every code or lock
# change a cache miss.
digest=$(python3 - vendor/*.whl vendor/constraints.txt <<'PY'
import hashlib, sys, zipfile
h = hashlib.sha256()
for path in sorted(sys.argv[1:]):
    if path.endswith(".whl"):
        with zipfile.ZipFile(path) as wheel:
            for name in sorted(wheel.namelist()):
                h.update(name.encode())
                h.update(wheel.read(name))
    else:
        with open(path, "rb") as f:
            h.update(f.read())
print(h.hexdigest())
PY
)
{
  cat requirements.in
  echo "-c ./vendor/constraints.txt"
  echo "# vendored wheels + constraints: ${digest}"
} > requirements.txt

echo "predeploy: bundled $(ls vendor | tr '\n' ' ')"
