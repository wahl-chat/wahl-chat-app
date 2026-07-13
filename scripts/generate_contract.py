# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
"""Generate CONTRACT.md from Pydantic model_json_schema() — do not hand-edit CONTRACT.md.

Phase 5 (D-10): src/matcher/ deleted — only ingestion/schemas.py models remain.
This script derives CONTRACT.md from ai-backend/src/ingestion/schemas.py.
The Matcher Models section has been removed; the Corpus Models section is now the
single source of truth for the data contract.

Run from the repo root:

    cd ai-backend && PYTHONPATH=src uv run python ../scripts/generate_contract.py

The file is written to CONTRACT.md at the repo root.
"""

import json
import pathlib
import sys

# ---------------------------------------------------------------------------
# Import models from the ai-backend src tree.
# Must be run with PYTHONPATH=ai-backend/src (or from ai-backend/ with PYTHONPATH=src).
# ---------------------------------------------------------------------------
try:
    from ingestion.schemas import (
        AuthorityTier,
        ChunkRecord,
        PledgeEventType,
        PledgeStatus,
        SourceType,
    )
    # Phase 5 (D-10): matcher.schemas deleted — no import from matcher
except ImportError as exc:
    print(
        f"ImportError: {exc}\n"
        "Run from ai-backend/ with:\n"
        "  PYTHONPATH=src uv run python ../scripts/generate_contract.py",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ROOT = pathlib.Path(__file__).parent.parent

SIGNOFF_PATH = pathlib.Path(__file__).parent / "contract_signoff.json"


def _field_type(info: dict) -> str:
    """Return a readable type string from a JSON Schema property dict."""
    if "anyOf" in info:
        # Optional[X] becomes anyOf: [{type: X}, {type: null}]
        non_null = [t for t in info["anyOf"] if t.get("type") != "null"]
        if non_null:
            return _field_type(non_null[0])
        return "null"
    if "allOf" in info:
        inner = info["allOf"][0]
        return inner.get("$ref", "").split("/")[-1] or _field_type(inner)
    if "$ref" in info:
        return info["$ref"].split("/")[-1]
    if "type" in info:
        ftype = info["type"]
        if ftype == "array":
            items = info.get("items", {})
            inner = _field_type(items) if items else "any"
            return f"array[{inner}]"
        return ftype
    return "any"


def _render_model(Model) -> list[str]:
    """Return Markdown lines for a single Pydantic model."""
    schema = Model.model_json_schema()
    doc = (Model.__doc__ or "").strip()
    lines = [
        f"## {Model.__name__}",
        "",
        doc,
        "",
        "| Field | Type | Required | Description |",
        "|-------|------|----------|-------------|",
    ]
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    for field, info in props.items():
        ftype = _field_type(info)
        req = "Yes" if field in required else "No"
        desc = info.get("description", "")
        lines.append(f"| `{field}` | `{ftype}` | {req} | {desc} |")
    lines.append("")
    return lines


def _render_enum(EnumCls) -> list[str]:
    """Return Markdown lines for a string enum."""
    doc = (EnumCls.__doc__ or "").strip()
    lines = [
        f"## {EnumCls.__name__}",
        "",
        doc,
        "",
        "| Value |",
        "|-------|",
    ]
    for member in EnumCls:
        lines.append(f"| `{member.value}` |")
    lines.append("")
    return lines


def _render_sc6_signoff() -> list[str]:
    """Return Markdown lines for the SC6 Review Sign-off section.

    Reads scripts/contract_signoff.json.  If the file is absent or status is
    not APPROVED, renders a clearly-marked "review pending" placeholder so the
    gate state is always visible and the generator never crashes.
    """
    placeholder = [
        "---",
        "",
        "## SC6 Review Sign-off",
        "",
        "> **Status:** PENDING",
        "> **Gate:** SC6 — derived/external pledge contract review not yet completed.",
        "> _(Update `scripts/contract_signoff.json` with status APPROVED to record approval.)_",
        "",
    ]

    if not SIGNOFF_PATH.exists():
        return placeholder

    try:
        data = json.loads(SIGNOFF_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return placeholder

    if data.get("status") != "APPROVED":
        return placeholder

    reviewer = data.get("reviewer", "")
    review_date = data.get("date", "")
    gate_desc = data.get("gate_description", "")
    decisions = data.get("decisions", {})
    unblocked = data.get("unblocked", "")
    superseded_note = data.get("superseded_note", "")

    lines = [
        "---",
        "",
        "## SC6 Review Sign-off",
        "",
        f"> **Status:** {data['status']}",
        f"> **Reviewer:** {reviewer}",
        f"> **Date:** {review_date}",
        f"> **Gate:** {gate_desc}",
    ]

    # Render the supersession note (if any) BEFORE the Phase-2 confirmations, so a
    # reader can't mistake the superseded Firestore-pledge design for current behaviour.
    if superseded_note:
        lines += [
            ">",
            f"> ⚠️ **Superseded.** {superseded_note}",
        ]

    lines += [
        ">",
        '> The "Derived / External Sources (Pledge Contract)" section above (Phase-2 pledge design:',
        "> PledgeStatus, PledgeEventType) has been reviewed and explicitly approved:",
        ">",
    ]

    # Emit decisions in sorted key order so output is stable across Python versions.
    for key in sorted(decisions.keys()):
        entry = decisions[key]
        confirmation = entry.get("confirmation", "")
        lines.append(f"> - {confirmation}")

    lines += [
        ">",
        f"> {unblocked}",
        "",
    ]
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    out: list[str] = []

    # Banner
    out += [
        "# wahl.chat V2 Data Contract",
        "",
        "_Auto-generated from Pydantic models — do not edit manually._",
        "_Regenerate with: `cd ai-backend && PYTHONPATH=src uv run python ../scripts/generate_contract.py`_",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # Corpus models (ingested → Firestore + Qdrant)
    # -----------------------------------------------------------------------
    out += [
        "## Corpus Models",
        "",
        "These models define the shape of data flowing through the ingestion pipeline into",
        "Qdrant (Phase 5: Firestore and GCS stores removed — D-10).",
        "",
    ]
    out += _render_model(ChunkRecord)

    # Enums used by corpus models
    out += [
        "### Corpus Enums",
        "",
    ]
    out += _render_enum(AuthorityTier)
    out += _render_enum(SourceType)

    # -----------------------------------------------------------------------
    # Derived / External Sources (Pledge Contract) — SC6
    # -----------------------------------------------------------------------
    out += [
        "---",
        "",
        "## Derived / External Sources (Pledge Contract)",
        "",
        "Pledge records represent the fulfillment status of political pledges tracked by",
        "external sources (e.g. the Cambridge PledgeTracker project). Phase 5 (D-04):",
        "pledges are embedded into Qdrant as ChunkRecords with `source_type=pledge_record`.",
        "The filterable fields `status`, `as_of_date`, and `claim_id` live on `ChunkRecord`",
        "(Qdrant payload indexes) — no separate Firestore pledges/ collection.",
        "",
        "**Key design decisions (D-04..D-06):**",
        "",
        "- **D-04:** Pledge records ARE embedded into Qdrant as ChunkRecords (Phase-5 reversal",
        "  of Phase-2 no-embed decision). `source_type=pledge_record` distinguishes them.",
        "- **D-05:** `status`, `as_of_date`, and `claim_id` are Qdrant payload fields",
        "  on ChunkRecord, enabling per-status / per-claim Qdrant filtering.",
        "- **D-06:** Pledge fulfillment status is public governmental commitment data, NOT",
        "  GDPR Art. 9 special-category data — embedding is permitted.",
        "- **Phase 5 removed:** `src/matcher/` package (Topic, Claim, Question,",
        "  QuestionStancePair Firestore models) — deleted in D-10.",
        "",
    ]
    # Pledge enums
    out += [
        "### Pledge Enums",
        "",
    ]
    out += _render_enum(PledgeStatus)
    out += _render_enum(PledgeEventType)

    # -----------------------------------------------------------------------
    # SC6 Review Sign-off (data-driven — reads scripts/contract_signoff.json)
    # -----------------------------------------------------------------------
    out += _render_sc6_signoff()

    # Write
    output_path = REPO_ROOT / "CONTRACT.md"
    output_path.write_text("\n".join(out), encoding="utf-8")
    print(f"Written {output_path}")


if __name__ == "__main__":
    main()
