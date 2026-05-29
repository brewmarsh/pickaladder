"""Tests for FirestorePaginator.
# ruff: noqa: PLR2004.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.cloud.firestore_v1.query import Query

from pickaladder.core.pagination import FirestorePaginator


@pytest.fixture
def mock_query() -> MagicMock:
    """Mock a Firestore Query."""
    return MagicMock(spec=Query)


def test_paginate_first_page_no_cursor(mock_query: MagicMock) -> None:
    """Test paginating the first page without a cursor."""
    results = [MagicMock(id=f"doc_{i}") for i in range(5)]
    mock_query.limit.return_value.stream.return_value = results

    limit_val = 4
    paged_results, next_cursor = FirestorePaginator.paginate(
        mock_query,
        limit=limit_val,
    )

    expected_len = 4
    assert len(paged_results) == expected_len
    assert next_cursor == "doc_3"
    mock_query.limit.assert_called_once_with(limit_val + 1)


def test_paginate_last_page(mock_query: MagicMock) -> None:
    """Test paginating the last page (no more results)."""
    results = [MagicMock(id=f"doc_{i}") for i in range(3)]
    mock_query.limit.return_value.stream.return_value = results

    limit_val = 4
    paged_results, next_cursor = FirestorePaginator.paginate(
        mock_query,
        limit=limit_val,
    )

    expected_len = 3
    assert len(paged_results) == expected_len
    assert next_cursor is None
    mock_query.limit.assert_called_once_with(limit_val + 1)


def test_paginate_empty_results(mock_query: MagicMock) -> None:
    """Test paginating when there are no results."""
    mock_query.limit.return_value.stream.return_value = []

    paged_results, next_cursor = FirestorePaginator.paginate(mock_query, limit=10)

    assert paged_results == []
    assert next_cursor is None


def test_paginate_with_cursor(mock_query: MagicMock) -> None:
    """Test paginating with a valid cursor_id."""
    mock_collection = MagicMock()
    mock_query._parent = mock_collection

    mock_cursor_doc = MagicMock()
    mock_cursor_doc.exists = True
    mock_collection.document.return_value.get.return_value = mock_cursor_doc

    mock_query_started = MagicMock()
    mock_query.start_after.return_value = mock_query_started

    results = [MagicMock(id=f"doc_{i}") for i in range(2)]
    mock_query_started.limit.return_value.stream.return_value = results

    paged_results, next_cursor = FirestorePaginator.paginate(
        mock_query,
        limit=2,
        cursor_id="cursor_123",
    )

    mock_collection.document.assert_called_once_with("cursor_123")
    mock_query.start_after.assert_called_once_with(mock_cursor_doc)

    expected_len = 2
    assert len(paged_results) == expected_len
    assert next_cursor is None


def test_paginate_invalid_cursor(mock_query: MagicMock) -> None:
    """Test paginating with a cursor_id that doesn't exist."""
    mock_collection = MagicMock()
    mock_query._parent = mock_collection

    mock_cursor_doc = MagicMock()
    mock_cursor_doc.exists = False
    mock_collection.document.return_value.get.return_value = mock_cursor_doc

    paged_results, next_cursor = FirestorePaginator.paginate(
        mock_query,
        limit=2,
        cursor_id="invalid_cursor",
    )

    assert paged_results == []
    assert next_cursor is None


def test_paginate_enforces_max_limit(mock_query: MagicMock) -> None:
    """Test that max limit is enforced."""
    mock_query.limit.return_value.stream.return_value = []

    FirestorePaginator.paginate(mock_query, limit=1000)

    mock_query.limit.assert_called_once_with(101)
