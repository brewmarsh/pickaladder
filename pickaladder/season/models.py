"""Data models for the season blueprint."""

from __future__ import annotations

from typing import Any, TypedDict


class Division(TypedDict, total=False):
    """Represents a sub-grouping within a season."""

    name: str
    participant_ids: list[str]
    visibility: str  # PUBLIC, UNLISTED, PRIVATE
    join_policy: str  # OPEN, REQUEST, INVITE


class MovementRules(TypedDict):
    """Rules for moving between divisions."""

    promotionCount: int
    relegationCount: int


class Season(TypedDict, total=False):
    """Represents a recurring competition season."""

    id: str
    name: str
    groupId: str
    startDate: Any  # Timestamp
    endDate: Any  # Timestamp
    status: str  # DRAFT, ACTIVE, COMPLETED, FINALIZING
    divisions: list[Division]
    movementRules: MovementRules
    finalStandings: list[dict[str, Any]]  # Snapshot of results
    createdAt: Any
    updatedAt: Any
