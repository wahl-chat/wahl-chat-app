# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""Debug logger for guided exploration — writes human-readable markdown logs."""

import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from src.guided_exploration.models.claim import Claim, PartyClaims
from src.guided_exploration.models.exploration import RetrievedChunk
from src.guided_exploration.models.tree import ExplorationNode, ExplorationTree

logger = logging.getLogger(__name__)

# Default log directory (relative to project root)
DEFAULT_LOG_DIR = "./debug_logs"

# Environment variable to enable debug logging
ENV_VAR = "DEBUG_EXPLORATION_LOG"


def is_debug_logging_enabled() -> bool:
    """Check if debug logging is enabled via environment variable."""
    return os.getenv(ENV_VAR, "").lower() in ("true", "1", "yes")


class DebugLogger:
    """
    Writes a human-readable markdown log file per exploration.

    Controlled by the DEBUG_EXPLORATION_LOG environment variable.
    When disabled, all methods are no-ops.
    """

    def __init__(
        self,
        session_id: str,
        query: str,
        parties: list[str],
        log_dir: str = DEFAULT_LOG_DIR,
    ):
        self._enabled = is_debug_logging_enabled()
        self._lines: list[str] = []
        self._file_path: Path | None = None

        if not self._enabled:
            return

        # Create log directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"exploration_{timestamp}_{session_id[:8]}.md"
        self._file_path = log_path / filename

        # Write header
        self._lines.append("# Exploration Debug Log")
        self._lines.append(f"- **Session**: `{session_id}`")
        self._lines.append(
            f"- **Timestamp**: {datetime.now(timezone.utc).isoformat()}"
        )
        self._lines.append(f'- **Query**: "{query}"')
        self._lines.append(f"- **Parties**: {', '.join(parties)}")
        self._lines.append("")

    @contextmanager
    def timed_section(self, title: str):
        """Context manager that logs a section with its duration."""
        if not self._enabled:
            yield
            return

        start = time.monotonic()
        self._lines.append(f"## {title}")
        yield
        elapsed_ms = (time.monotonic() - start) * 1000
        self._lines.append(f"\n*Duration: {elapsed_ms:.0f}ms*\n")

    def log_rag_retrieval(
        self,
        party_id: str,
        party_name: str,
        chunks: list[RetrievedChunk],
        duration_ms: float,
    ) -> None:
        """Log RAG retrieval results for a party."""
        if not self._enabled:
            return

        self._lines.append(f"### Party: {party_name} (`{party_id}`)")
        self._lines.append(f"- Chunks retrieved: {len(chunks)}")
        if chunks:
            scores = [c.relevance_score for c in chunks]
            self._lines.append(
                f"- Score range: {min(scores):.3f} - {max(scores):.3f}"
            )
            self._lines.append(f"- Duration: {duration_ms:.0f}ms")
            self._lines.append("- Top chunks:")
            for i, chunk in enumerate(chunks[:3]):
                preview = chunk.content[:120].replace("\n", " ")
                self._lines.append(
                    f"  {i + 1}. [{chunk.source_document} p.{chunk.source_page}] "
                    f'"{preview}..."'
                )
        else:
            self._lines.append("- *No chunks retrieved*")
        self._lines.append("")

    def log_claim_extraction(
        self,
        party_id: str,
        party_name: str,
        party_claims: PartyClaims,
        duration_ms: float,
    ) -> None:
        """Log claim extraction results for a party."""
        if not self._enabled:
            return

        self._lines.append(f"### Party: {party_name} (`{party_id}`)")
        self._lines.append(f"- Claims extracted: {len(party_claims.claims)}")
        self._lines.append(
            f"- Relevance to query: {party_claims.relevance_to_query:.2f}"
        )
        self._lines.append(f"- Duration: {duration_ms:.0f}ms")
        self._lines.append("- Claims:")
        for i, claim in enumerate(party_claims.claims, 1):
            self._lines.append(
                f'  {i}. [{claim.claim_type}] "{claim.content}" '
                f"[chunk {claim.chunk_index}]"
            )
        self._lines.append("")

    def log_hierarchy_construction(
        self,
        tree: ExplorationTree,
        total_claims: int,
        party_count: int,
        duration_ms: float,
    ) -> None:
        """Log hierarchy construction results."""
        if not self._enabled:
            return

        self._lines.append(
            f"- Total claims input: {total_claims} across {party_count} parties"
        )
        self._lines.append(f"- Duration: {duration_ms:.0f}ms")
        self._lines.append("- Tree structure:")
        self._log_node(tree.root, indent=1)
        self._lines.append("")

    def _log_node(self, node: ExplorationNode, indent: int = 0) -> None:
        """Recursively log tree node structure."""
        prefix = "  " * indent
        party_info = f"({len(node.party_ids)} parties: {', '.join(node.party_ids)})"
        leaf_marker = " [LEAF]" if node.is_leaf else ""
        claims_info = (
            f" — {len(node.claim_ids)} claims" if node.claim_ids else ""
        )
        self._lines.append(
            f"{prefix}- **{node.name}**{leaf_marker} {party_info}{claims_info}"
        )
        for child in node.children:
            self._log_node(child, indent + 1)

    def log_content_generation(
        self,
        leaf_id: str,
        leaf_name: str,
        claims_used: int,
        parties: list[str],
        duration_ms: float,
    ) -> None:
        """Log content generation for a leaf navigation."""
        if not self._enabled:
            return

        self._lines.append(f"### Leaf: {leaf_name} (`{leaf_id}`)")
        self._lines.append(f"- Claims used: {claims_used}")
        self._lines.append(f"- Parties: {', '.join(parties)}")
        self._lines.append(f"- Duration: {duration_ms:.0f}ms")
        self._lines.append("")

    def log_message(self, message: str) -> None:
        """Log a free-form message."""
        if not self._enabled:
            return
        self._lines.append(message)
        self._lines.append("")

    def flush(self) -> None:
        """Write all buffered log lines to the file."""
        if not self._enabled or self._file_path is None:
            return

        try:
            self._file_path.write_text("\n".join(self._lines), encoding="utf-8")
            logger.info(f"Debug log written to {self._file_path}")
        except Exception as e:
            logger.warning(f"Failed to write debug log: {e}")
