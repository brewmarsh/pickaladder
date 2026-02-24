from __future__ import annotations

from firebase_admin import firestore

from .calculator import MatchStatsCalculator
from .command import MatchCommandService
from .formatting import MatchFormatter
from .query import MatchQueryService


# Backward compatibility alias
class MatchService(MatchQueryService, MatchCommandService):  # type: ignore
    """Deprecated alias for MatchQueryService and MatchCommandService."""

    pass


__all__ = [
    "MatchQueryService",
    "MatchCommandService",
    "MatchStatsCalculator",
    "MatchFormatter",
    "MatchService",
    "firestore",
]
