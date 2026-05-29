"""Core data types for the pickaladder application."""

from __future__ import annotations

from typing import Any, Dict, TypedDict  # noqa: UP035


class _FirestoreDocumentBase(TypedDict):
    id: str
    createdAt: Any


class FirestoreDocument(_FirestoreDocumentBase, total=False):
    """Generic Firestore document structure."""

    path: str
    updatedAt: Any


class APIResponse(TypedDict):
    """Generic API response structure."""

    success: bool
    message: str
    data: Dict[str, Any] | None  # noqa: UP006
