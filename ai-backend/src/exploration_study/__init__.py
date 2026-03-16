"""
Exploration Study Module.

This module manages user studies comparing baseline chat vs guided exploration.
It includes:
- Admin API for creating studies and pre-generating participant sessions
- Participant API for study flow (consent -> demographics -> tasks -> questionnaires)
- Quiz generation and scoring for knowledge retention measurement
"""


def get_facade():
    """Get the exploration study facade (lazy import to avoid circular imports)."""
    from src.exploration_study.facade import get_facade as _get_facade

    return _get_facade()


__all__ = [
    "get_facade",
]
