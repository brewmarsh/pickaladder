"""Common utilities for tests."""

from mockfirestore import CollectionReference, Query
from mockfirestore.document import DocumentReference


def patch_mockfirestore():
    """Apply monkeypatches to mockfirestore to support FieldFilter and equality."""

    def collection_where(self, field_path=None, op_string=None, value=None, filter=None):
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
        DocumentReference.__hash__ = lambda self: hash(tuple(self._path))
