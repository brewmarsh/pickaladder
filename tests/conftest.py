"""Common utilities for tests."""

import unittest.mock

from mockfirestore import CollectionReference, Query
from mockfirestore.document import DocumentReference


class MockArrayUnion:
    def __init__(self, values):
        self.values = values

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)


class MockArrayRemove:
    def __init__(self, values):
        self.values = values

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)


def patch_mockfirestore():
    """Apply monkeypatches to mockfirestore to support FieldFilter and equality."""

    def collection_where(
        self, field_path=None, op_string=None, value=None, filter=None
    ):  # noqa: E501
        if filter:
            return self._where(filter.field_path, filter.op_string, filter.value)
        return self._where(field_path, op_string, value)

    if not hasattr(CollectionReference, "_where"):
        CollectionReference._where = CollectionReference.where
        CollectionReference.where = collection_where

    def query_where(self, field_path=None, op_string=None, value=None, filter=None):
        if filter:
            return self._where(filter.field_path, filter.op_string, filter.value)
        return self._where(field_path, op_string, value)

    if not hasattr(Query, "_where"):
        Query._where = Query.where
        Query.where = query_where

    def doc_ref_eq(self, other):
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

        def patched_update(self, data):
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
    def __init__(self, db):
        self.db = db
        self.updates = []
        self.commit = unittest.mock.MagicMock(side_effect=self._real_commit)

    def update(self, ref, data):
        self.updates.append((ref, data))

    def set(self, ref, data, merge=False):
        # For set with merge=True, it's like update.
        # For simplicity in tests, we just update.
        self.updates.append((ref, data))

    def delete(self, ref):
        self.updates.append((ref, "DELETE"))

    def _real_commit(self):
        for ref, data in self.updates:
            if data == "DELETE":
                ref.delete()
            else:
                ref.update(data)
