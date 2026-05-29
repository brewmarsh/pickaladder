"""Utility functions and classes for the user blueprint."""

from __future__ import annotations

from typing import Any


class CursorPagination:
    """A pagination object for cursor-based results."""

    def __init__(self, items: list[Any], next_cursor: str | None = None) -> None:
        """Initialize the cursor pagination object."""
        self.items = items
        self.next_cursor = next_cursor
        self.has_next = next_cursor is not None
        # pages is kept for template compatibility
        self.pages = 2 if self.has_next else 1
