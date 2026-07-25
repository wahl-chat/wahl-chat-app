#!/usr/bin/env bash
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
#
# Restore a Qdrant collection from a snapshot file — local dev OR a remote Qdrant
# (e.g. the initial-data upload into a dev/prod store). Wraps Qdrant's
# "recover from uploaded snapshot" endpoint and verifies the restored point count.
#
# Usage:
#   scripts/restore_qdrant_snapshot.sh \
#       --snapshot PATH \
#       --collection NAME \
#       [--qdrant-url URL]      (default: http://localhost:6333)
#       [--api-key KEY]         (default: $QDRANT_API_KEY)
#       [--force]               (allow overwriting an existing non-empty collection)
#       [--yes]                 (skip the confirmation prompt for a REMOTE target)
#
# The snapshot upload REPLACES the target collection's contents. As a safety net
# the script refuses to clobber an existing non-empty collection without --force,
# and requires an explicit confirmation when the target is not localhost (so an
# initial prod upload can't happen by a stray command).
set -euo pipefail

SNAPSHOT="" COLLECTION="" QDRANT_URL="http://localhost:6333"
API_KEY="${QDRANT_API_KEY:-}" FORCE=0 ASSUME_YES=0

die() { echo "ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --snapshot)   SNAPSHOT="$2"; shift 2 ;;
    --collection) COLLECTION="$2"; shift 2 ;;
    --qdrant-url) QDRANT_URL="${2%/}"; shift 2 ;;
    --api-key)    API_KEY="$2"; shift 2 ;;
    --force)      FORCE=1; shift ;;
    --yes)        ASSUME_YES=1; shift ;;
    -h|--help)    sed -n '2,26p' "$0"; exit 0 ;;
    *)            die "unknown argument: $1" ;;
  esac
done

[[ -n "$SNAPSHOT"   ]] || die "--snapshot is required"
[[ -n "$COLLECTION" ]] || die "--collection is required"
[[ -f "$SNAPSHOT"   ]] || die "snapshot file not found: $SNAPSHOT"

# curl auth header (only when a key is set).
AUTH=()
[[ -n "$API_KEY" ]] && AUTH=(-H "api-key: ${API_KEY}")

# Expand AUTH safely even when empty (bash 3.2 + set -u).
q() { curl -sS ${AUTH[@]+"${AUTH[@]}"} "$@"; }

echo "Target   : ${QDRANT_URL}  collection='${COLLECTION}'"
echo "Snapshot : ${SNAPSHOT} ($(du -h "$SNAPSHOT" | cut -f1))"

# Guard 1: existing non-empty collection needs --force.
EXISTING=$(q "${QDRANT_URL}/collections/${COLLECTION}" || true)
COUNT=$(printf '%s' "$EXISTING" | python3 -c \
  "import sys,json;\
r=(json.load(sys.stdin) or {}).get('result');\
print((r or {}).get('points_count') if r else 'MISSING')" 2>/dev/null || echo "MISSING")
if [[ "$COUNT" != "MISSING" && "$COUNT" != "None" && "$COUNT" != "0" ]]; then
  [[ "$FORCE" == "1" ]] || die "collection '${COLLECTION}' already has ${COUNT} points — pass --force to overwrite."
  echo "WARNING: overwriting existing collection with ${COUNT} points (--force)."
fi

# Guard 2: a non-localhost target is a real (dev/prod) store — confirm.
if [[ "$QDRANT_URL" != *localhost* && "$QDRANT_URL" != *127.0.0.1* && "$ASSUME_YES" != "1" ]]; then
  read -r -p "Target is REMOTE (${QDRANT_URL}). Type the collection name to confirm: " CONFIRM
  [[ "$CONFIRM" == "$COLLECTION" ]] || die "confirmation did not match — aborting."
fi

echo "Uploading + recovering ..."
RESP=$(q -X POST \
  "${QDRANT_URL}/collections/${COLLECTION}/snapshots/upload?priority=snapshot" \
  -H "Content-Type:multipart/form-data" \
  -F "snapshot=@${SNAPSHOT}")
OK=$(printf '%s' "$RESP" | python3 -c \
  "import sys,json;print((json.load(sys.stdin) or {}).get('status'))" 2>/dev/null || echo "")
[[ "$OK" == "ok" ]] || die "recover failed: ${RESP}"

# Verify.
RESTORED=$(q "${QDRANT_URL}/collections/${COLLECTION}" | python3 -c \
  "import sys,json;r=json.load(sys.stdin)['result'];print(r['points_count'],r['status'])")
echo "Restored : ${RESTORED% *} points (status: ${RESTORED#* })"
echo "Done."
