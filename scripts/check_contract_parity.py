# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Assert the GENERATED-PAIR modules are identical in ai-backend/ and ingestion/.

The packages are independent (see AGENTS.md), so these modules are duplicated on
purpose. Permitted differences: the local package prefix on imports, and comments
and docstrings, which name their own package's paths.

Run from the repo root: uv run python scripts/check_contract_parity.py
"""

import difflib
import json
import re
import sys
from pathlib import Path

BACKEND = Path("ai-backend/src")
INGESTION = Path("ingestion/src/ingestion")
CONTRACT = Path("corpus-contract.json")

PAIRED_MODULES = [
    "corpus_contract.py",
    "corpus.py",
    "governance_levels.py",
    "legislature_config.py",
    "embeddings.py",
    "vertex_credentials.py",
]

# The one thing a duplicated module cannot share: its own package prefix.
_IMPORT_SWAP = (
    (re.compile(r"\bsrc\.corpus_contract\b"), "<pkg>.corpus_contract"),
    (re.compile(r"\bingestion\.corpus_contract\b"), "<pkg>.corpus_contract"),
    (re.compile(r"\bsrc\.corpus\b"), "<pkg>.corpus"),
    (re.compile(r"\bingestion\.corpus\b"), "<pkg>.corpus"),
    (re.compile(r"\bsrc\.vertex_credentials\b"), "<pkg>.vertex_credentials"),
    (re.compile(r"\bingestion\.vertex_credentials\b"), "<pkg>.vertex_credentials"),
)


def _normalize(text: str) -> list[str]:
    """Fold the package prefix to <pkg> and drop comments."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern, replacement in _IMPORT_SWAP:
            line = pattern.sub(replacement, line)
        out.append(line)
    return out


def _strip_docstrings(source: str) -> str:
    """Drop docstrings so only executable code is compared."""
    import ast

    tree = ast.parse(source)
    spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            doc = body[0]
            spans.append((doc.lineno, doc.end_lineno or doc.lineno))
    drop = {n for start, end in spans for n in range(start, end + 1)}
    return "\n".join(
        line for num, line in enumerate(source.splitlines(), 1) if num not in drop
    )


def main() -> int:
    if not CONTRACT.is_file():
        print(
            f"FAIL: {CONTRACT} not found. Run from the repo root.",
            file=sys.stderr,
        )
        return 1

    try:
        json.loads(CONTRACT.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: {CONTRACT} is not valid JSON: {exc}", file=sys.stderr)
        return 1

    failures = 0
    for module in PAIRED_MODULES:
        left, right = BACKEND / module, INGESTION / module
        missing = [str(p) for p in (left, right) if not p.is_file()]
        if missing:
            print(f"FAIL: {module} — missing copy: {missing}", file=sys.stderr)
            failures += 1
            continue

        a = _normalize(_strip_docstrings(left.read_text(encoding="utf-8")))
        b = _normalize(_strip_docstrings(right.read_text(encoding="utf-8")))
        if a != b:
            failures += 1
            print(f"FAIL: {module} has diverged between the two packages:")
            for line in list(
                difflib.unified_diff(a, b, str(left), str(right), lineterm="", n=2)
            )[:40]:
                print(f"  {line}")

    if failures:
        print(
            f"\n{failures} paired module(s) diverged. These files are duplicated on "
            "purpose (the packages are independent) — apply the edit to BOTH copies.",
            file=sys.stderr,
        )
        return 1

    print(f"PASS: {len(PAIRED_MODULES)} paired modules identical across both packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
