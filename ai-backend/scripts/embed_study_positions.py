# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
Compute OpenAI embeddings for the study position JSON files.

Reads the 5 per-party JSONs in `ai-backend/data/study-fake-parties/positions/`,
embeds each position's ``content`` with ``text-embedding-3-large``, and writes
one consolidated file ``positions_embedded.json`` in the same directory.

The output file is the runtime source of truth for the in-memory study RAG
resolver — see ``services/study_positions_rag.py``.

Idempotent: positions whose content has already been embedded (same id + same
content hash) are skipped on re-runs. Delete the output file to force a full
re-embedding.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Load OPENAI_API_KEY (and other env vars) from ai-backend/.env before any
# langchain imports trigger client initialization.
from src.utils import load_env  # noqa: E402

load_env()

from langchain_openai import OpenAIEmbeddings  # noqa: E402

# Locate the repo-relative data directory using this script's location.
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data" / "study-fake-parties"
POSITIONS_DIR = DATA_DIR / "positions"
OUTPUT_FILE = DATA_DIR / "positions_embedded.json"

EMBEDDING_MODEL = "text-embedding-3-large"


def content_hash(text: str) -> str:
    """Return a short deterministic fingerprint of a position's content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_all_positions() -> list[dict]:
    """Load and concatenate all per-party position files."""
    positions: list[dict] = []
    party_files = sorted(p for p in POSITIONS_DIR.glob("*.json"))
    if not party_files:
        print(f"No position files found in {POSITIONS_DIR}", file=sys.stderr)
        sys.exit(1)

    for f in party_files:
        data = json.loads(f.read_text(encoding="utf-8"))
        print(f"  {f.name}: {len(data)} positions")
        positions.extend(data)
    return positions


def load_existing_embeddings() -> dict[str, dict]:
    """Load existing embeddings keyed by id, if any."""
    if not OUTPUT_FILE.exists():
        return {}
    try:
        existing = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Could not parse existing {OUTPUT_FILE.name}: {e} — rebuilding.")
        return {}
    return {p["id"]: p for p in existing}


def main() -> None:
    print(f"Loading positions from {POSITIONS_DIR}")
    positions = load_all_positions()
    print(f"Total: {len(positions)} positions")

    if len({p["id"] for p in positions}) != len(positions):
        print("ERROR: duplicate position ids detected", file=sys.stderr)
        sys.exit(1)

    existing = load_existing_embeddings()
    print(f"Existing embedded file: {len(existing)} positions cached")

    # Determine which positions need (re-)embedding.
    to_embed: list[dict] = []
    for p in positions:
        h = content_hash(p["content"])
        cached = existing.get(p["id"])
        if cached and cached.get("content_hash") == h and "embedding" in cached:
            continue
        to_embed.append(p)

    print(f"Positions needing embedding: {len(to_embed)}")

    if to_embed:
        model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        texts = [p["content"] for p in to_embed]
        print(f"Calling OpenAI ({EMBEDDING_MODEL}) for {len(texts)} positions...")
        vectors = model.embed_documents(texts)
        for p, vec in zip(to_embed, vectors):
            existing[p["id"]] = {
                **p,
                "content_hash": content_hash(p["content"]),
                "embedding": vec,
            }
        print(f"Embedded {len(to_embed)} positions ({len(vectors[0])}-dim)")
    else:
        print("Nothing to embed — all positions already up to date.")

    # Build output in the order of the source files.
    ordered_ids = [p["id"] for p in positions]
    output_data = [existing[pid] for pid in ordered_ids]

    OUTPUT_FILE.write_text(
        json.dumps(output_data, ensure_ascii=False), encoding="utf-8"
    )
    size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    print(f"Wrote {len(output_data)} positions → {OUTPUT_FILE} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
