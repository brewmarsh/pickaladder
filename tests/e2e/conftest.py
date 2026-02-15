"""Test configuration and mocks for end-to-end tests."""

from __future__ import annotations

import importlib
import os
import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from mockfirestore import CollectionReference, MockFirestore, Transaction
from mockfirestore.document import DocumentReference, DocumentSnapshot
from mockfirestore.query import Query
from werkzeug.serving import make_server

if TYPE_CHECKING:
    from collections.abc import Generator

# --- Mock Infrastructure & Patches ---

# Fix mockfirestore Query.get to return a list instead of generator
def query_get(self: Query) -> list[DocumentSnapshot]:
    """Return a list instead of generator."""
    return list(self.stream())

Query.get = query_get  # type: ignore[method-assign]

# Patch CollectionReference.where
original_collection_where = CollectionReference.where

def collection_where(
    self: CollectionReference,
    field_path: str | None = None,
    op_string: str | None = None,
    value: Any = None,
    filter: Any = None,
) -> Query:
    """Handle FieldFilter argument in where."""
    if filter:
        return original_collection_where(
            self, filter.field_path, filter.op_string, filter.value
        )
    return original_collection_where(self, field_path, op_string, value)

CollectionReference.where = collection_where  # type: ignore[assignment]

# Patch Query.where
original_where = Query.where

def query_where(
    self: Query,
    field_path: str | None = None,
    op_string: str | None = None,
    value: Any = None,
    filter: Any = None,
) -> Query:
    """Handle FieldFilter argument in where."""
    if filter:
        return original_where(self, filter.field_path, filter.op_string, filter.value)
    return original_where(self, field_path, op_string, value)

Query.where = query_where  # type: ignore[assignment]

# Patch Query._compare_func
original_compare_func = Query._compare_func  # type: ignore[attr-defined]

def query_compare_func(self: Query, op: str) -> Any:
    """Handle document ID comparisons and array_contains."""
    if op == "in":
        def in_op(x: Any, y: list[Any]) -> bool:
            """Handle 'in' operator mock."""
            normalized_y = []
            for item in y:
                if hasattr(item, "id"):
                    normalized_y.append(item.id)
                else:
                    normalized_y.append(item)
            x_val = x
            if hasattr(x, "id"):
                x_val = x.id
            return x_val in normalized_y
        return in_op
    elif op == "array_contains":
        def array_contains_op(x: list[Any] | None, y: Any) -> bool:
            """Handle 'array_contains' operator mock."""
            if x is None:
                return False
            return y in x
        return array_contains_op
    return original_compare_func(self, op)

Query._compare_func = query_compare_func  # type: ignore[attr-defined]

# Patch DocumentSnapshot._get_by_field_path
original_get_by_field_path = DocumentSnapshot._get_by_field_path  # type: ignore[attr-defined]

def get_by_field_path(self: DocumentSnapshot, field_path: str) -> Any:
    """Handle __name__ field path."""
    if field_path == "__name__":
        return self.id
    return original_get_by_field_path(self, field_path)

DocumentSnapshot._get_by_field_path = get_by_field_path  # type: ignore[attr-defined]

# Patch DocumentReference.get to handle transaction argument
original_get = DocumentReference.get

def doc_ref_get(self: DocumentReference, transaction: Any = None) -> DocumentSnapshot:
    """Handle transaction argument in get."""
    return original_get(self)

DocumentReference.get = doc_ref_get  # type: ignore[method-assign]

# Patch DocumentReference equality and hashing
def doc_ref_eq(self: DocumentReference, other: Any) -> bool:
    """Equality for DocumentReference."""
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path

def doc_ref_hash(self: DocumentReference) -> int:
    """Hash for DocumentReference."""
    return hash(tuple(self._path))

DocumentReference.__eq__ = doc_ref_eq  # type: ignore[method-assign]
DocumentReference.__hash__ = doc_ref_hash  # type: ignore[method-assign]

# Handle ArrayUnion/ArrayRemove
class MockSentinel:
    """Mock sentinel for array operations."""
    def __init__(self, values: list[Any], op: str) -> None:
        self.values = values
        self.op = op
    def __iter__(self) -> Any:
        return iter(self.values)

def mock_array_union(values: list[Any]) -> MockSentinel:
    return MockSentinel(values, "UNION")

def mock_array_remove(values: list[Any]) -> MockSentinel:
    return MockSentinel(values, "REMOVE")

original_update = DocumentReference.update

def doc_ref_update(self: DocumentReference, data: dict[str, Any]) -> None:
    """Update document handling sentinels and nested fields."""
    sentinels = {k: v for k, v in data.items() if isinstance(v, MockSentinel)}
    others = {k: v for k, v in data.items() if not isinstance(v, MockSentinel)}

    if others:
        original_update(self, others)

    if sentinels:
        doc_snapshot = self.get()
        doc_data = doc_snapshot.to_dict() if doc_snapshot.exists else {}
        for key, value in sentinels.items():
            current_list = doc_data.get(key, [])
            if not isinstance(current_list, list):
                current_list = []
            if value.op == "UNION":
                for item in value.values:
                    if item not in current_list:
                        current_list.append(item)
            elif value.op == "REMOVE":
                for item in value.values:
                    if item in current_list:
                        current_list.remove(item)
            doc_data[key] = current_list
        self.set(doc_data)

DocumentReference.update = doc_ref_update  # type: ignore[method-assign]

# --- Mock Classes ---

class MockFieldFilter:
    """Mock for firestore.FieldFilter."""
    def __init__(self, field_path: str, op_string: str, value: Any) -> None:
        self.field_path = field_path
        self.op_string = op_string
        self.value = value

class MockBatch:
    """Mock for firestore.WriteBatch."""
    def __init__(self, client: Any) -> None:
        self.client = client
        self.ops: list[Any] = []
    def set(self, doc_ref: DocumentReference, data: dict[str, Any], merge: bool = False) -> None:
        self.ops.append(("set", doc_ref, data, merge))
    def update(self, doc_ref: DocumentReference, data: dict[str, Any]) -> None:
        self.ops.append(("update", doc_ref, data))
    def delete(self, doc_ref: DocumentReference) -> None:
        self.ops.append(("delete", doc_ref))
    def commit(self) -> None:
        for op in self.ops:
            if op[0] == "set":
                op[1].set(op[2], merge=op[3])
            elif op[0] == "update":
                op[1].update(op[2])
            elif op[0] == "delete":
                op[1].delete()
        self.ops = []

class MockTransaction(Transaction):
    """Mock for firestore.Transaction."""
    def __init__(self, db: EnhancedMockFirestore) -> None:
        self.db = db
        self._read_only = False
        self._id = "mock-transaction-id"
        self._max_attempts = 5
        self._retry_id = None

    def _begin(self, **kwargs: Any) -> None:
        """Mock begin."""
        pass

    def _rollback(self) -> None:
        """Mock rollback."""
        pass

    def _commit(self) -> list[Any]:
        """Mock commit."""
        return []

    def _clean_up(self) -> None:
        """Mock clean up."""
        pass

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            return MagicMock()
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def get(self, ref_or_query: Any, **kwargs: Any) -> Any:
        return ref_or_query.get()

    def set(self, reference: Any, document_data: Any, merge: bool = False) -> None:
        reference.set(document_data, merge=merge)

    def update(self, reference: Any, field_updates: dict[str, Any], option: Any = None) -> None:
        reference.update(field_updates)

    def delete(self, reference: Any, option: Any = None) -> None:
        reference.delete()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

class EnhancedMockFirestore(MockFirestore):
    """Enhanced MockFirestore with batch and transaction support."""
    def __init__(self) -> None:
        super().__init__()
    def collection(self, name: str) -> CollectionReference:
        if name not in self._data:
            self._data[name] = {}
        return super().collection(name)
    def batch(self) -> MockBatch:
        return MockBatch(self)
    def transaction(self) -> MockTransaction:
        return MockTransaction(self)

# --- MockAuthService and Fixtures remain as defined in context ---