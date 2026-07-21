#!/bin/sh
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
#
# Link provider-specific agent-instruction files to the committed source of truth.
#
# AGENTS.md is the single, committed agent/onboarding document. Some assistants
# (e.g. Claude Code) look for a provider-specific CLAUDE.md instead, so we point
# it at AGENTS.md via a symlink. The symlink is git-ignored — only AGENTS.md is
# committed — so this script is how each clone materialises CLAUDE.md locally.
#
# Usage (from anywhere):
#     ./scripts/setup-agent-docs.sh
#
# Idempotent: re-running replaces any existing CLAUDE.md (real file or stale
# symlink) with a fresh symlink to AGENTS.md.

set -eu

# Resolve the repo root from this script's location so it works from any cwd.
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ ! -f AGENTS.md ]; then
    echo "ERROR: AGENTS.md not found in $repo_root — nothing to link." >&2
    exit 1
fi

# -f: overwrite an existing regular file or symlink in place (idempotent).
ln -sf AGENTS.md CLAUDE.md

echo "Linked CLAUDE.md -> AGENTS.md"
