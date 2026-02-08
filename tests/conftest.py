"""Common utilities for tests."""

import unittest.mock
from typing import Any, Iterator, Optional

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


def patch_mockfirestore() -> None:
    """Apply monkeypatches to mockfirestore to support FieldFilter and equality."""

    def collection_where(
        self: Any,
        field_path: Optional[str] = None,
        op_string: Optional[str] = None,
        value: Any = None,
        filter: Any = None,
    ) -> Any:  # noqa: E501
        if filter:
            return self._where(filter.field_path, filter.op_string, filter.value)
        return self._where(field_path, op_string, value)

    if not hasattr(CollectionReference, "_where"):
        CollectionReference._where = CollectionReference.where
        CollectionReference.where = collection_where

    def query_where(
        self: Any,
        field_path: Optional[str] = None,
        op_string: Optional[str] = None,
        value: Any = None,
        filter: Any = None,
    ) -> Any:
        if filter:
            return self._where(filter.field_path, filter.op_string, filter.value)
        return self._where(field_path, op_string, value)

    if not hasattr(Query, "_where"):
        Query._where = Query.where
        Query.where = query_where

    def doc_ref_eq(self: Any, other: Any) -> bool:
        if not isinstance(other, DocumentReference):
            return False
        return self._path == other._path

    if not hasattr(DocumentReference, "_orig_eq"):
        DocumentReference._orig_eq = DocumentReference.__eq__
        DocumentReference.__eq__ = doc_ref_eq

    if not hasattr(DocumentReference, "__hash__"):
        DocumentReference.__hash__ = lambda self: hash(tuple(self._path))

    if not hasattr(DocumentReference, "_orig_update"):
        DocumentReference._orig_update = DocumentReference.update

        def patched_update(self: Any, data: dict[str, Any]) -> Any:
            current_data = self.get().to_dict() or {}
            new_data = {}
            for k, v in data.items():
                if isinstance(v, MockArrayUnion):
                    existing = current_data.get(k, [])
                    if not isinstance(existing, list):
                        existing = []
                    # Simple append for mock, firestore does set union
                    merged = list(existing)
                    for item in v.values:
                        if item not in merged:
                            merged.append(item)
                    new_data[k] = merged
                elif isinstance(v, MockArrayRemove):
                    existing = current_data.get(k, [])
                    if not isinstance(existing, list):
                        existing = []
                    new_data[k] = [i for i in existing if i not in v.values]
                else:
                    new_data[k] = v
            # MockFirestore's DocumentReference.update just updates its internal _data
            # We use the original update to ensure any other logic is preserved
            return self._orig_update(new_data)

        DocumentReference.update = patched_update


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
