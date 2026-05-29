"""Data models for social activity tracking."""

from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict


class ActivityType(str, Enum):
    """Supported community event types."""

    MATCH_COMPLETED = "MATCH_COMPLETED"
    SEASON_FINALIZED = "SEASON_FINALIZED"
    RANK_CHANGE = "RANK_CHANGE"
    TOURNAMENT_WIN = "TOURNAMENT_WIN"


class Activity(TypedDict, total=False):
    """Represents a social event in the community feed."""

    id: str
    userId: str  # The primary actor
    type: str  # ActivityType
    data: dict[str, Any]  # Event-specific payload (e.g., scores, season name)
    timestamp: Any  # Firestore Timestamp
    reactions: list[dict[str, Any]]  # Future-proofing for engagement
