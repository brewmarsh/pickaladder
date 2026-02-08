"""Core data types for the pickaladder application."""

from typing import Any, Dict, Optional, TypedDict  # noqa: UP035


class _FirestoreDocumentBase(TypedDict):
    id: str
    created_at: Any


class FirestoreDocument(_FirestoreDocumentBase, total=False):
    """Generic Firestore document structure."""

    path: str
    updated_at: Any


class APIResponse(TypedDict):
    """Generic API response structure."""

    success: bool
    message: str
    data: Optional[Dict[str, Any]]  # noqa: UP006
