# SPDX-License-Identifier: Apache-2.0
"""Static GDPR Art. 9 wall guard.

Asserts that no file under ingestion/src/ references a `users/` Firestore path
in live code (the ingestion package is the only in-scope tree). Political
opinion data must never be read by corpus/ingestion code.

The scan walks the AST, so comments and docstrings that mention `users/` as
security documentation never trigger it, and forbidden calls split across
multiple lines are still caught. Files that fail to parse fall back to a
whole-text regex scan (over-matching is acceptable for a guard; silently
skipping a file is not).

Run from the repo root:

    python scripts/check_gdpr_wall.py
    # or via uv:
    uv run python scripts/check_gdpr_wall.py
"""

import ast
import glob
import re
import sys
from pathlib import Path

# Fallback pattern for files that do not parse as Python. Matches the same
# access shapes as the AST scan, quote-anchored so prose mentions of users/
# do not trigger it.
FALLBACK_PATTERN = re.compile(
    r'collection\(\s*["\']users["\'/]'
    r'|\.document\(\s*["\']users/'
    r"|collection_group\("
    r'|db\[\s*["\']users["\'/]'
)

# Paths are relative to the repo root so the script runs identically from CI
# and locally regardless of cwd — as long as cwd is the repo root.
SCAN_GLOBS = [
    "ingestion/src/ingestion/**/*.py",
    # The ingestion package is the only tree in scope for the GDPR Art. 9 wall.
    # retrieve.py lives in ai-backend/ and is a READ path over the corpus, which
    # never touches users/ — the wall is about what corpus code may read.
]


def _is_users_path(value: object) -> bool:
    """True if a literal argument/key addresses the users collection tree."""
    return isinstance(value, str) and (value == "users" or value.startswith("users/"))


def _call_name(node: ast.Call) -> str:
    """Bare name of the called function (`collection` for both f() and o.f())."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _first_str_arg(node: ast.Call) -> object:
    if node.args and isinstance(node.args[0], ast.Constant):
        return node.args[0].value
    return None


def _find_violations(tree: ast.AST) -> list[tuple[int, str]]:
    """Collect (lineno, reason) for every forbidden Firestore access shape.

    Forbidden:
      - collection("users") / collection("users/...")  — collection access
      - document("users/...")                          — direct document path
      - collection_group(...)                          — ANY collection-group
        query (it scans every subcollection with that name across all users,
        so it is forbidden in ingestion code regardless of argument)
      - db["users"] / db["users/..."]                  — mapping-style access
        on a name/attribute called `db`
    """
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name == "collection_group":
                violations.append((node.lineno, "collection_group(...) query"))
            elif name in ("collection", "document"):
                if _is_users_path(_first_str_arg(node)):
                    violations.append((node.lineno, f'{name}(...) on a users/ path'))
        elif isinstance(node, ast.Subscript):
            base = node.value
            base_name = (
                base.id
                if isinstance(base, ast.Name)
                else base.attr
                if isinstance(base, ast.Attribute)
                else ""
            )
            if base_name == "db" and isinstance(node.slice, ast.Constant):
                if _is_users_path(node.slice.value):
                    violations.append((node.lineno, 'db["users"] access'))
    return violations


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
            try:
                tree = ast.parse(source, filename=path)
            except SyntaxError:
                # Unparseable file: regex over the raw text so nothing is
                # silently skipped. Docstring false positives are acceptable
                # here — a broken file should be fixed either way.
                for lineno, line in enumerate(source.splitlines(), 1):
                    if FALLBACK_PATTERN.search(line):
                        violations.append((path, lineno, line.strip()))
                continue
            for lineno, reason in _find_violations(tree):
                violations.append((path, lineno, reason))

    # Non-vacuous guard: fail if the glob matched zero files. A zero-file scan
    # would pass silently even if the glob pattern is broken.
    if not scanned:
        print(
            "FAIL: SCAN_GLOBS matched zero files — glob may be misconfigured "
            f"(patterns: {SCAN_GLOBS}). Check that ingestion/src/ingestion/ exists "
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
        for path, lineno, detail in violations:
            print(f"  {path}:{lineno}: {detail}")
        return 1

    print("PASS: no Firestore users/ collection access found in ingestion/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
