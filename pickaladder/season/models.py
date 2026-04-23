"""Data models for the season blueprint."""

from __future__ import annotations

from typing import Any, TypedDict


class Division(TypedDict, total=False):
    """Represents a sub-grouping within a season."""
    name: str
    participant_ids: list[str]


class Season(TypedDict, total=False):
    """Represents a recurring competition season."""
    id: str
    name: str
    groupId: str
    startDate: Any  # Timestamp
    endDate: Any    # Timestamp
    status: str     # DRAFT, ACTIVE, COMPLETED
    divisions: list[Division]
    createdAt: Any
    updatedAt: Any
