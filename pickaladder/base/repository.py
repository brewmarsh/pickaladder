from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


class BaseRepository:
    """Standardize Firestore CRUD operations."""

    COLLECTION_NAME: str = ""

    @classmethod
    def get_by_id(cls, db: Client, doc_id: str) -> dict[str, Any] | None:
        """Fetch a single document by its ID."""
        if not cls.COLLECTION_NAME:
            raise NotImplementedError("COLLECTION_NAME must be defined in subclasses.")

        doc_ref = db.collection(cls.COLLECTION_NAME).document(doc_id)
        doc_snap = cast("DocumentSnapshot", doc_ref.get())
        if not doc_snap.exists:
            return None
        data = doc_snap.to_dict() or {}
        data["id"] = doc_id
        return data

    @classmethod
    def create(cls, db: Client, data: dict[str, Any]) -> str:
        """Create a new document and return its ID."""
        if not cls.COLLECTION_NAME:
            raise NotImplementedError("COLLECTION_NAME must be defined in subclasses.")

        doc_ref = db.collection(cls.COLLECTION_NAME).document()
        doc_ref.set(data)
        return doc_ref.id

    @classmethod
    def update(cls, db: Client, doc_id: str, data: dict[str, Any]) -> None:
        """Update an existing document."""
        if not cls.COLLECTION_NAME:
            raise NotImplementedError("COLLECTION_NAME must be defined in subclasses.")

        doc_ref = db.collection(cls.COLLECTION_NAME).document(doc_id)
        doc_snap = cast("DocumentSnapshot", doc_ref.get())
        if not doc_snap.exists:
            raise ValueError(f"Document not found in {cls.COLLECTION_NAME}: {doc_id}")
        doc_ref.update(data)

    @classmethod
    def delete(cls, db: Client, doc_id: str) -> None:
        """Delete a document by its ID."""
        if not cls.COLLECTION_NAME:
            raise NotImplementedError("COLLECTION_NAME must be defined in subclasses.")

        db.collection(cls.COLLECTION_NAME).document(doc_id).delete()
