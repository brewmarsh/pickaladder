from __future__ import annotations

from typing import Any, TypeVar

from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1.query import Query

T = TypeVar('T')


class FirestorePaginator:
    """Utility for cursor-based pagination in Firestore."""

    MAX_LIMIT = 100

    @staticmethod
    def paginate(
        query: Query,
        limit: int,
        cursor_id: str | None = None,
    ) -> tuple[list[DocumentSnapshot], str | None]:
        """
        Paginate a Firestore query.

        Args:
            query: The base Firestore query (including order_by).
            limit: Maximum number of items to return.
            cursor_id: Document ID to start after.

        Returns:
            A tuple containing:
            - list of DocumentSnapshot
            - next_cursor (str) or None if no more pages.
        """
        # Enforce maximum limit to prevent DoS
        actual_limit = min(max(1, limit), FirestorePaginator.MAX_LIMIT)

        # If cursor is provided, get the document and start after it
        if cursor_id:
            # We need the actual document snapshot to use start_after
            # Usually, the query's parent is the collection
            # query._parent gives us the collection reference in google-cloud-firestore
            # but we need to be careful with mockfirestore or different versions.

            # For simplicity and compatibility, we can try to fetch the cursor document
            # using the collection associated with the query.
            # In google-cloud-firestore, query._parent is the collection.
            # In mockfirestore, query.parent might be it.

            try:
                # Try to get collection from query
                collection = getattr(query, '_parent', getattr(query, 'parent', None))
                if collection:
                    cursor_doc = collection.document(cursor_id).get()
                    if cursor_doc.exists:
                        query = query.start_after(cursor_doc)
                    else:
                        # If cursor doc doesn't exist, return empty result to be safe
                        return [], None
            except Exception:
                # Handle cases where query structure is unexpected
                return [], None

        # Fetch one extra to determine if there is a next page
        results = list(query.limit(actual_limit + 1).stream())

        if not results:
            return [], None

        has_next = len(results) > actual_limit
        paged_results = results[:actual_limit]

        next_cursor = paged_results[-1].id if has_next else None

        return paged_results, next_cursor
