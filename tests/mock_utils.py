from firebase_admin import firestore

"""Mock utilities for Firestore and Auth."""

import unittest.mock
from collections.abc import Iterator
from typing import Any, Optional

from mockfirestore import CollectionReference, Query
from mockfirestore.document import DocumentReference


class MockArrayUnion:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


class MockArrayRemove:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def __iter__(self) -> Iterator[Any]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)


class MockBatch:
    def __init__(self, db: Any) -> None:
        self.db = db
        self.updates: list[tuple[Any, Any]] = []
        self.commit = unittest.mock.MagicMock(side_effect=self._real_commit)

    def update(self, ref: Any, data: Any) -> None:
        self.updates.append((ref, data))

    def set(self, ref: Any, data: Any, merge: bool = False) -> None:
        # For set with merge=True, it's like update.
        # For simplicity in tests, we just update.
        self.updates.append((ref, data))

    def delete(self, ref: Any) -> None:
        self.updates.append((ref, "DELETE"))

    def _real_commit(self) -> None:
        for ref, data in self.updates:
            if data == "DELETE":
                ref.delete()
            else:
                ref.update(data)


def _apply_array_union(current_list: list[Any], values: list[Any]) -> list[Any]:
    """Apply union operation."""
    merged = list(current_list)
    for item in values:
        if item not in merged:
            merged.append(item)
    return merged


def _apply_array_operation(
    current_list: list[Any], sentinel: MockArrayUnion | MockArrayRemove
) -> list[Any]:
    """Apply ArrayUnion or ArrayRemove operation to a list."""
    if isinstance(sentinel, MockArrayUnion):
        return _apply_array_union(current_list, sentinel.values)
    # Must be MockArrayRemove
    return [i for i in current_list if i not in sentinel.values]


def _handle_sentinel_updates(
    doc_ref: Any, sentinels: dict[str, MockArrayUnion | MockArrayRemove]
) -> dict[str, list[Any]]:
    """Process sentinel updates and return the new data dictionary."""
    current_data = doc_ref.get().to_dict() or {}
    new_data = {}
    for k, v in sentinels.items():
        existing = current_data.get(k, [])
        if not isinstance(existing, list):
            existing = []
        new_data[k] = _apply_array_operation(existing, v)
    return new_data


def _patched_update(self: Any, data: dict[str, Any]) -> Any:
    """Internal update method that handles sentinels."""
    sentinels = {
        k: v
        for k, v in data.items()
        if isinstance(v, (MockArrayUnion, MockArrayRemove))
    }
    others = {
        k: v
        for k, v in data.items()
        if not isinstance(v, (MockArrayUnion, MockArrayRemove))
    }

    if others:
        self._orig_update(others)

    if sentinels:
        new_data = _handle_sentinel_updates(self, sentinels)
        # MockFirestore's DocumentReference.update updates its internal _data.
        # Use the original update to ensure any other logic is preserved.
        return self._orig_update(new_data)
    return None


def _where_impl(
    self: Any,
    field_path: Optional[str] = None,
    op_string: Optional[str] = None,
    value: Any = None,
    filter: Any = None,
) -> Any:
    """Implementation of where that handles FieldFilter."""
    if filter:
        return self._where(filter.field_path, filter.op_string, filter.value)
    return self._where(field_path, op_string, value)


def _patched_compare_func(self: Any, op: str) -> Any:
    """Patched comparison function for Query."""
    if op == "array_contains":
        return lambda x, y: x is not None and y in x
    return self._orig_compare_func(op)


def _doc_ref_eq(self: Any, other: Any) -> bool:
    """Equality for DocumentReference."""
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path


def _doc_ref_hash_fn(self: Any) -> int:
    """Hash for DocumentReference."""
    return hash(tuple(self._path))


def _patched_doc_ref_get(self: Any, transaction: Any = None) -> Any:
    """Handle transaction argument in get."""
    return self._orig_get()


class MockFirestoreBuilder:
    """Builder to modularize mockfirestore and firebase_admin patching."""

    @staticmethod
    def _patch_where_methods() -> None:
        """Patch CollectionReference and Query where methods to support FieldFilter."""
        if not hasattr(CollectionReference, "_where"):
            CollectionReference._where = CollectionReference.where
            CollectionReference.where = _where_impl

        if not hasattr(Query, "_where"):
            Query._where = Query.where
            Query.where = _where_impl

    @staticmethod
    def _patch_doc_ref_identity() -> None:
        """Patch DocumentReference equality and hashing."""
        if not hasattr(DocumentReference, "_orig_eq"):
            DocumentReference._orig_eq = DocumentReference.__eq__
            DocumentReference.__eq__ = _doc_ref_eq

        if not hasattr(DocumentReference, "__hash__"):
            DocumentReference.__hash__ = _doc_ref_hash_fn

    @staticmethod
    def _patch_query_comparison() -> None:
        """Patch Query._compare_func to handle array_contains safely."""
        if not hasattr(Query, "_orig_compare_func"):
            Query._orig_compare_func = Query._compare_func
            Query._compare_func = _patched_compare_func

    @staticmethod
    def _patch_doc_ref_get() -> None:
        """Patch DocumentReference.get to handle transaction argument."""
        if not hasattr(DocumentReference, "_orig_get"):
            DocumentReference._orig_get = DocumentReference.get
            DocumentReference.get = _patched_doc_ref_get

    @staticmethod
    def patch_db_read() -> None:
        """Apply monkeypatches to mockfirestore to support FieldFilter and equality."""
        MockFirestoreBuilder._patch_where_methods()
        MockFirestoreBuilder._patch_doc_ref_identity()
        MockFirestoreBuilder._patch_query_comparison()
        MockFirestoreBuilder._patch_doc_ref_get()

    @staticmethod
    def patch_db_write() -> None:
        """Apply monkeypatches to mockfirestore to support update with sentinels."""
        if not hasattr(DocumentReference, "_orig_update"):
            DocumentReference._orig_update = DocumentReference.update
            DocumentReference.update = _patched_update

    @staticmethod
    def patch_db_auth() -> unittest.mock.MagicMock:
        """Create an autospec'd mock for firebase_admin.auth."""
        from firebase_admin import auth

        return unittest.mock.create_autospec(auth, spec_set=True)


def patch_mockfirestore() -> None:
    """Apply monkeypatches to mockfirestore to support FieldFilter and equality."""
    MockFirestoreBuilder.patch_db_read()
    MockFirestoreBuilder.patch_db_write()
