"""
Migration script to rename created_at to createdAt in teams
and group_invites collections.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.batch import WriteBatch

import firebase_admin
from firebase_admin import credentials, firestore

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def _load_credentials() -> credentials.Certificate | None:
    """Load Firebase credentials from file or environment variable."""
    # Check common credential filenames
    for filename in ["serviceAccountKey.json", "firebase_credentials.json"]:
        cred_path = project_root / filename
        if cred_path.exists():
            return credentials.Certificate(str(cred_path))

    import json
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        try:
            return credentials.Certificate(json.loads(cred_json))
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def initialize_firebase() -> bool:
    """Initializes the Firebase Admin SDK."""
    if firebase_admin._apps:
        return True
    cred = _load_credentials()
    if not cred:
        # If no creds, we might be in emulator mode if FIRESTORE_EMULATOR_HOST is set
        if os.environ.get("FIRESTORE_EMULATOR_HOST"):
             firebase_admin.initialize_app()
             return True
        print("Error: No credentials found and FIRESTORE_EMULATOR_HOST not set.")
        return False

    firebase_admin.initialize_app(cred)
    return True


def migrate_collection(
    db: Any,
    collection_name: str,
    dry_run: bool = False,
    batch_size: int = 500,
) -> None:
    """Rename created_at to createdAt in the specified collection."""
    print(f"Migrating collection: {collection_name}")
    # Detect if we're using mockfirestore
    is_mock = hasattr(db, "reset") or "MockFirestore" in str(type(db))
    batch: WriteBatch | None = db.batch() if not dry_run and not is_mock else None
    count, total = 0, 0

    for doc in db.collection(collection_name).stream():
        total += 1
        data = doc.to_dict()
        if "created_at" in data:
            updates = {
                "createdAt": data["created_at"],
                "created_at": firestore.DELETE_FIELD
            }
            if dry_run:
                print(f"[DRY] {doc.id}: {updates}")
                count += 1
            elif is_mock:
                doc.reference.update(updates)
                count += 1
            elif batch:
                batch.update(doc.reference, updates)
                count += 1
                if count % batch_size == 0:
                    batch.commit()
                    batch = db.batch()

    if batch and count % batch_size != 0:
        batch.commit()
    print(f"Done {collection_name}. Processed: {total}, Migrated: {count}\n")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    if not initialize_firebase():
        sys.exit(1)

    db = firestore.client()

    collections = ["teams", "group_invites"]
    for coll in collections:
        migrate_collection(db, coll, args.dry_run, args.batch_size)


if __name__ == "__main__":
    main()
