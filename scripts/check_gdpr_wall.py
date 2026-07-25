# SPDX-License-Identifier: Apache-2.0
"""Static GDPR Art. 9 wall guard.

Asserts that no file under ai-backend/src/ingestion/ references a `users/`
Firestore path in live code (ingestion/ is the only in-scope tree). Political
opinion data must never be read by corpus/ingestion code.

Comments and docstrings that mention `users/` as security documentation are
allowed — only actual Firestore collection access patterns are forbidden.

Run from the repo root:

    python scripts/check_gdpr_wall.py
    # or via uv:
    uv run --project ai-backend python scripts/check_gdpr_wall.py
"""

import glob
import re
import sys
from pathlib import Path

# Pattern for ACTUAL Firestore users/ collection access (not docstring mentions).
# Matches:
#   - collection("users") / .collection('users')
#   - .document("users/...") / .document('users/...')  — direct document-path access
#   - collection_group(...)                            — ANY collection-group query
#     (a collection-group query scans every subcollection with that name across
#      all users, so it is forbidden in ingestion code regardless of argument)
#   - db["users"] style access
# Does NOT match bare 'users/' in security comments/docstrings.
FORBIDDEN_PATTERN = re.compile(
    r'collection\(["\']users["\']'
    r'|\.document\(["\']users/'
    r"|collection_group\("
    r"|db\[.?users"
)

# Paths are relative to the repo root so the script runs identically from CI
# and locally regardless of cwd — as long as cwd is the repo root.
SCAN_GLOBS = [
    "ai-backend/src/ingestion/**/*.py",
    # ingestion/ is the only tree in scope for the GDPR Art. 9 wall.
]


def _is_code_line(line: str) -> bool:
    """Return True if the line is executable code (not a comment or pure docstring line)."""
    stripped = line.strip()
    # Skip blank lines
    if not stripped:
        return False
    # Skip comment lines
    if stripped.startswith("#"):
        return False
    # Skip lines that are just a docstring delimiter or pure docstring text
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return False
    return True


def main() -> int:
    scanned: list[str] = []
    violations: list[tuple[str, int, str]] = []

    for pattern in SCAN_GLOBS:
        for path in glob.glob(pattern, recursive=True):
            scanned.append(path)
            try:
                source = Path(path).read_text(encoding="utf-8")
            except OSError as exc:
                print(f"WARN: could not read {path}: {exc}", file=sys.stderr)
                continue
            for lineno, line in enumerate(source.splitlines(), 1):
                if _is_code_line(line) and FORBIDDEN_PATTERN.search(line):
                    violations.append((path, lineno, line.strip()))

    # Non-vacuous guard (Pitfall 4): fail if the glob matched zero files.
    # A zero-file scan would pass silently even if the glob pattern is broken.
    if not scanned:
        print(
            "FAIL: SCAN_GLOBS matched zero files — glob may be misconfigured "
            f"(patterns: {SCAN_GLOBS}). Check that ai-backend/src/ingestion/ exists "
            "and the pattern is correct.",
            file=sys.stderr,
        )
        return 1

    print(f"Scanned {len(scanned)} file(s) in ingestion/")

    if violations:
        print(
            f"FAIL: {len(violations)} line(s) access the Firestore users/ collection "
            "in ingestion/ code:"
        )
        for path, lineno, line in violations:
            print(f"  {path}:{lineno}: {line}")
        return 1

    print("PASS: no Firestore users/ collection access found in ingestion/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
