"""Service for persisting and managing application errors."""

from __future__ import annotations

import traceback
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore
from flask import g, request

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class ErrorService:
    """Service for managing system errors and health metrics."""

    COLLECTION_NAME = "system_errors"

    @classmethod
    def log_error(
        cls,
        exception: Exception,
        request_context: Any | None = None,
    ) -> str | None:
        """Persist a server-side error to Firestore."""
        try:
            db: Client = firestore.client()

            error_data = {
                "message": str(exception),
                "type": exception.__class__.__name__,
                "stack_trace": traceback.format_exc(),
                "timestamp": firestore.SERVER_TIMESTAMP,
                "url": request.url if request else "N/A",
                "method": request.method if request else "N/A",
                "user_id": g.user.uid
                if (hasattr(g, "user") and g.user)
                else "anonymous",
                "user_agent": request.headers.get("User-Agent") if request else "N/A",
                "resolved": False,
            }

            # Optional additional context
            if request_context:
                error_data["context"] = request_context

            doc_ref = db.collection(cls.COLLECTION_NAME).add(error_data)
            return doc_ref[1].id
        except Exception as e:
            # Fallback to standard logging if Firestore fails to avoid recursive loops
            import logging

            logging.exception(f"Failed to log error to Firestore: {e}")
            return None

    @classmethod
    def get_recent_errors(cls, db: Client, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch the most recent system errors."""
        docs = (
            db.collection(cls.COLLECTION_NAME)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() | {"id": doc.id} for doc in docs]  # type: ignore
