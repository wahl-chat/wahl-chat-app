# SPDX-FileCopyrightText: 2025 wahl.chat
#
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0

"""
In-memory retrieval for the study's fake party positions.

The study uses a fixed, finite set of ~200 manually authored positions across
5 fictional parties and 2 topics. Because the set is tiny and static, we avoid
Qdrant entirely: precomputed embeddings are loaded into a numpy matrix at
startup, and cosine similarity is evaluated in-memory per query.

The resolver returns ``RetrievedChunk`` objects so it is a drop-in replacement
for ``RAGService.retrieve_chunks_for_party`` when the session's context_id
indicates a study topic (``study-klimaschutz`` / ``study-soziale-gerechtigkeit``).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
from langchain_core.embeddings import Embeddings

from src.guided_exploration.models.exploration import RetrievedChunk

logger = logging.getLogger(__name__)

# Default location for the embedded positions file produced by
# ``scripts/embed_study_positions.py``.
_DEFAULT_POSITIONS_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "study-fake-parties"
    / "positions_embedded.json"
)


class StudyPositionsRAG:
    """
    In-memory similarity search over the study's fake party positions.

    Loaded lazily from ``positions_embedded.json``. Filters by party_id and
    topic and returns the top-N positions by cosine similarity.
    """

    def __init__(
        self,
        embeddings: Embeddings,
        positions_file: Path | None = None,
    ) -> None:
        self._embeddings = embeddings
        path = positions_file or _DEFAULT_POSITIONS_FILE

        if not path.exists():
            raise FileNotFoundError(
                f"Study positions file not found at {path}. "
                f"Run scripts/embed_study_positions.py first."
            )

        logger.info(f"Loading study positions from {path}")
        with path.open(encoding="utf-8") as f:
            raw: list[dict] = json.load(f)

        if not raw:
            raise ValueError(f"No positions in {path}")

        self._positions: list[dict] = raw

        # Build the embedding matrix and pre-normalize for cosine similarity.
        matrix = np.array([p["embedding"] for p in raw], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        # Guard against zero vectors (shouldn't happen but be safe).
        norms[norms == 0] = 1.0
        self._matrix_normalized: np.ndarray = matrix / norms

        # Pre-index by (party_id, topic) so we can filter with a single
        # numpy gather instead of scanning all rows per query.
        index_by_key: dict[tuple[str, str], list[int]] = {}
        for i, p in enumerate(raw):
            key = (p["party_id"], p["topic"])
            index_by_key.setdefault(key, []).append(i)
        self._indices_by_key: dict[tuple[str, str], np.ndarray] = {
            k: np.array(v, dtype=np.int64) for k, v in index_by_key.items()
        }

        logger.info(
            f"Loaded {len(raw)} study positions across "
            f"{len({p['party_id'] for p in raw})} parties and "
            f"{len({p['topic'] for p in raw})} topics "
            f"(embedding dim {self._matrix_normalized.shape[1]})"
        )

    async def retrieve_chunks_for_party(
        self,
        query: str,
        party_id: str,
        topic: str,
        n_docs: int = 10,
    ) -> list[RetrievedChunk]:
        """
        Return the top-N positions for ``party_id`` on ``topic``, ranked by
        cosine similarity against the query embedding.
        """
        key = (party_id, topic)
        indices = self._indices_by_key.get(key)
        if indices is None or len(indices) == 0:
            logger.warning(
                f"No study positions for party={party_id}, topic={topic}"
            )
            return []

        # Embed query and normalize.
        query_vec_list = await self._embeddings.aembed_query(query)
        query_vec = np.array(query_vec_list, dtype=np.float32)
        q_norm = float(np.linalg.norm(query_vec))
        if q_norm == 0.0:
            logger.warning("Zero-norm query embedding")
            return []
        query_vec = query_vec / q_norm

        # Cosine similarity — dot product since both sides are unit vectors.
        candidate_matrix = self._matrix_normalized[indices]
        scores = candidate_matrix @ query_vec

        # Top-k
        k = min(n_docs, len(scores))
        top_local = np.argpartition(-scores, k - 1)[:k]
        # Sort those k by score descending
        top_local = top_local[np.argsort(-scores[top_local])]

        chunks: list[RetrievedChunk] = []
        for local_idx in top_local:
            global_idx = int(indices[local_idx])
            pos = self._positions[global_idx]
            chunks.append(
                RetrievedChunk(
                    chunk_id=pos["id"],
                    content=pos["content"],
                    party_id=pos["party_id"],
                    source_document=f"{pos['party_id'].title()}-Wahlprogramm",
                    source_section=None,
                    source_page=None,
                    relevance_score=float(scores[local_idx]),
                    metadata={
                        "topic": pos["topic"],
                        "position_id": pos["id"],
                        "url": f"/exploration-study/sources/{pos['party_id']}#{pos['id']}",
                    },
                )
            )

        logger.info(
            f"Study RAG: party={party_id} topic={topic} "
            f"returned {len(chunks)}/{len(indices)} positions"
        )
        return chunks

    @property
    def position_count(self) -> int:
        """Total number of positions loaded."""
        return len(self._positions)
