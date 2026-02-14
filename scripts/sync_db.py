"""
Database synchronization script to mirror Production data to the Beta environment.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any

import firebase_admin
from firebase_admin import credentials, firestore

FIRESTORE_BATCH_LIMIT = 500

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.collection import CollectionReference


class BatchProcessor:
    """Handles batched Firestore operations to respect the 500-limit."""

    def __init__(self, db: Client):
        self.db = db
        self.batch = db.batch()
        self.count = 0

    def set(self, ref: Any, data: dict[str, Any]) -> None:
        """Adds a set operation to the batch."""
        self.batch.set(ref, data)
        self.count += 1
        if self.count >= FIRESTORE_BATCH_LIMIT:
            self.commit()

    def delete(self, ref: Any) -> None:
        """Adds a delete operation to the batch."""
        self.batch.delete(ref)
        self.count += 1
        if self.count >= FIRESTORE_BATCH_LIMIT:
            self.commit()

    def commit(self) -> None:
        """Commits the current batch."""
        if self.count > 0:
            self.batch.commit()
            self.batch = self.db.batch()
            self.count = 0


def initialize_apps() -> tuple[firebase_admin.App, firebase_admin.App]:
    """Initializes the two Firebase apps for Production (Source) and Beta (Destination)."""
    prod_key_path = os.environ.get("PROD_KEY_PATH")
    beta_key_path = os.environ.get("BETA_KEY_PATH")

    if not prod_key_path or not beta_key_path:
        print(
            "Error: PROD_KEY_PATH and BETA_KEY_PATH environment variables must be set."
        )
        sys.exit(1)

    # Initialize Prod App (Source)
    prod_cred = credentials.Certificate(prod_key_path)
    prod_app = firebase_admin.initialize_app(prod_cred, name="prod")

    # Initialize Beta App (Destination)
    beta_cred = credentials.Certificate(beta_key_path)
    beta_app = firebase_admin.initialize_app(beta_cred, name="beta")

    return prod_app, beta_app


def delete_collection_recursive(
    coll_ref: CollectionReference, batch_processor: BatchProcessor
) -> None:
    """Recursively adds all documents in a collection and its subcollections to the delete batch."""
    for doc_ref in coll_ref.list_documents():
        # Recursively handle subcollections
        for sub_coll in doc_ref.collections():
            delete_collection_recursive(sub_coll, batch_processor)
        batch_processor.delete(doc_ref)


def copy_collection_recursive(
    src_coll: CollectionReference,
    dest_coll: CollectionReference,
    batch_processor: BatchProcessor,
) -> int:
    """Recursively copies all documents from one collection to another using batching."""
    count = 0
    for doc_snap in src_coll.stream():
        data = doc_snap.to_dict()
        if data is None:
            continue

        dest_doc = dest_coll.document(doc_snap.id)
        batch_processor.set(dest_doc, data)
        count += 1

        # Recurse for subcollections
        for sub_coll in doc_snap.reference.collections():
            count += copy_collection_recursive(
                sub_coll, dest_doc.collection(sub_coll.id), batch_processor
            )
    return count


def sync_collection(collection_name: str, prod_db: Client, beta_db: Client) -> None:
    """Syncs a single collection from production to beta."""
    print(f"Syncing collection: {collection_name}...")

    # Safety Check: Ensure destination project ID contains 'beta' or 'sandbox'
    project_id = beta_db.project
    if not project_id or (
        "beta" not in project_id.lower() and "sandbox" not in project_id.lower()
    ):
        print(
            f"CRITICAL ERROR: Destination project ID '{project_id}' does not "
            "contain 'beta' or 'sandbox'."
        )
        print(
            "Delete operations are restricted to beta/sandbox environments for safety."
        )
        sys.exit(1)

    prod_coll = prod_db.collection(collection_name)
    beta_coll = beta_db.collection(collection_name)

    # 1. Cleanup beta (Delete all existing documents in this collection)
    print(f"  Cleaning up beta collection '{collection_name}'...")
    batch_del = BatchProcessor(beta_db)
    delete_collection_recursive(beta_coll, batch_del)
    batch_del.commit()

    # 2. Read from prod and write to beta
    print(f"  Copying data from production collection '{collection_name}'...")
    batch_set = BatchProcessor(beta_db)
    total_copied = copy_collection_recursive(prod_coll, beta_coll, batch_set)
    batch_set.commit()
    print(f"  Done. Copied {total_copied} documents (including subcollections).")


def main() -> None:
    """Main entry point for the sync script."""
    try:
        prod_app, beta_app = initialize_apps()
        prod_db = firestore.client(app=prod_app)
        beta_db = firestore.client(app=beta_app)

        # Critical collections to sync as per requirements
        collections_to_sync = ["users", "matches", "groups", "tournaments"]

        for coll in collections_to_sync:
            sync_collection(coll, prod_db, beta_db)

        print("\nDatabase sync completed successfully.")
    except Exception as e:
        print(f"\nAn error occurred during sync: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
