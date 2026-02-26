"""
Migration script to normalize historical match data to the new unified schema.

This script:
- Normalizes scores (player1_score -> player1Score).
- Compiles 'participants' list of UIDs.
- Determines 'winners' and 'losers' arrays.
- Updates documents with new fields.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, cast

import firebase_admin
from firebase_admin import credentials, firestore

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def _get_credentials_path() -> Path:
    """Get the path to the Firebase credentials file."""
    return project_root / "firebase_credentials.json"


def _load_certificate(path_or_dict: Any) -> credentials.Certificate | None:
    """Helper to load a certificate with error handling."""
    try:
        return credentials.Certificate(path_or_dict)
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def _load_credentials() -> credentials.Certificate | None:
    """Load Firebase credentials from file or environment variable."""
    cred_path = _get_credentials_path()
    if cred_path.exists():
        return _load_certificate(str(cred_path))

    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        try:
            return _load_certificate(json.loads(cred_json))
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing FIREBASE_CREDENTIALS_JSON: {e}")

    print("Could not find Firebase credentials.")
    return None


def initialize_firebase() -> bool:
    """Initializes the Firebase Admin SDK."""
    if firebase_admin._apps:
        return True

    cred = _load_credentials()
    if not cred:
        return False

    bucket = os.environ.get("FIREBASE_STORAGE_BUCKET") or "pickaladder.firebasestorage.app"
    firebase_admin.initialize_app(cred, {"storageBucket": bucket})
    return True


def main() -> None:
    """Main entry point for the migration script."""
    parser = argparse.ArgumentParser(description="Migrate match data to v10 schema.")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without committing.")
    parser.add_argument("--batch-size", type=int, default=100, help="Number of documents per batch.")
    parser.add_argument("--mock", action="store_true", help="Use a mock database for testing.")
    args = parser.parse_args()

    if args.mock:
        from mockfirestore import MockFirestore
        db = _setup_mock_db()
        print("Using Mock Database.")
    else:
        if not initialize_firebase():
            print("Failed to initialize Firebase.")
            sys.exit(1)
        db = firestore.client()
        print("Connected to Live Firestore.")

    migrate_matches(db, dry_run=args.dry_run, batch_size=args.batch_size)


def _get_ids_from_refs(refs: Any) -> list[str]:
    """Extract string IDs from a list of references or strings."""
    if not refs:
        return []
    if not isinstance(refs, list):
        refs = [refs]
    return [str(r.id if hasattr(r, "id") else r) for r in refs if r]


def _extract_uids(data: dict[str, Any]) -> list[str]:
    """Compile a flat list of participant UIDs from various possible fields."""
    uids: set[str] = set()

    # Check singles fields
    for field in ["player1Ref", "player2Ref", "player1", "player2"]:
        val = data.get(field)
        if val:
            uids.add(str(val.id if hasattr(val, "id") else val))

    # Check doubles fields
    for field in ["team1", "team2"]:
        uids.update(_get_ids_from_refs(data.get(field)))

    # Check legacy/denormalized fields
    if "player_1_data" in data and isinstance(data["player_1_data"], dict):
        uid = data["player_1_data"].get("uid")
        if uid:
            uids.add(str(uid))
    if "player_2_data" in data and isinstance(data["player_2_data"], dict):
        uid = data["player_2_data"].get("uid")
        if uid:
            uids.add(str(uid))

    # Fallback to existing participants if any
    if "participants" in data:
        uids.update(_get_ids_from_refs(data["participants"]))

    return sorted(list(uids))


def _normalize_scores(data: dict[str, Any]) -> tuple[int, int]:
    """Normalize scores from various possible field names."""
    s1 = data.get("player1Score")
    if s1 is None:
        s1 = data.get("player1_score")
    if s1 is None:
        s1 = 0

    s2 = data.get("player2Score")
    if s2 is None:
        s2 = data.get("player2_score")
    if s2 is None:
        s2 = 0

    try:
        return int(s1), int(s2)
    except (ValueError, TypeError):
        return 0, 0


def _get_sides(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Determine UIDs for side 1 and side 2."""
    is_doubles = data.get("matchType") == "doubles" or data.get("match_type") == "doubles"

    if is_doubles:
        s1 = _get_ids_from_refs(data.get("team1"))
        s2 = _get_ids_from_refs(data.get("team2"))
        return s1, s2

    # Singles
    p1_ref = data.get("player1Ref")
    p1_id = str(p1_ref.id if hasattr(p1_ref, "id") else p1_ref) if p1_ref else ""
    if not p1_id and "player_1_data" in data:
        p1_id = data["player_1_data"].get("uid", "")

    p2_ref = data.get("player2Ref")
    p2_id = str(p2_ref.id if hasattr(p2_ref, "id") else p2_ref) if p2_ref else ""
    if not p2_id and "player_2_data" in data:
        p2_id = data["player_2_data"].get("uid", "")

    return ([p1_id] if p1_id else []), ([p2_id] if p2_id else [])


def _calculate_outcome(data: dict[str, Any], s1: int, s2: int) -> dict[str, Any]:
    """Determine winner/loser arrays and IDs."""
    side1, side2 = _get_sides(data)

    if s1 == s2:
        return {
            "winner": "draw",
            "winnerId": None,
            "loserId": None,
            "winners": [],
            "losers": [],
        }

    winner_side = "team1" if s1 > s2 else "team2"

    # winnerId/loserId are typically first player or team ID
    # For migration, we'll try to keep it consistent with MatchStatsCalculator
    s1_id = data.get("team1Id") or (side1[0] if side1 else None)
    s2_id = data.get("team2Id") or (side2[0] if side2 else None)

    return {
        "winner": winner_side,
        "winnerId": s1_id if winner_side == "team1" else s2_id,
        "loserId": s2_id if winner_side == "team1" else s1_id,
        "winners": side1 if winner_side == "team1" else side2,
        "losers": side2 if winner_side == "team1" else side1,
    }


def migrate_matches(db: Any, dry_run: bool = False, batch_size: int = 100) -> None:
    """Iterate through all matches and normalize them."""
    matches_ref = db.collection("matches")
    docs = matches_ref.stream()

    total_processed = 0
    total_migrated = 0

    # Check if mock DB (mockfirestore 0.x might not support batch)
    is_mock = hasattr(db, "reset") or "MockFirestore" in str(type(db))

    batch = None
    if not dry_run and not is_mock:
        batch = db.batch()

    batch_count = 0

    for doc in docs:
        total_processed += 1
        data = doc.to_dict()
        updates = _get_match_updates(data)

        if not updates:
            continue

        total_migrated += 1
        if dry_run:
            print(f"[DRY-RUN] Match {doc.id}: {updates}")
        elif is_mock:
            doc.reference.update(updates)
        else:
            batch.update(doc.reference, updates)
            batch_count += 1
            if batch_count >= batch_size:
                batch.commit()
                print(f"Committed batch of {batch_count} matches.")
                batch = db.batch()
                batch_count = 0

    if not dry_run and not is_mock and batch_count > 0:
        batch.commit()
        print(f"Committed final batch of {batch_count} matches.")

    print(f"\nMigration complete. Processed: {total_processed}, Migrated: {total_migrated}")


def _get_match_updates(data: dict[str, Any]) -> dict[str, Any]:
    """Determine necessary updates for a single match document."""
    updates: dict[str, Any] = {}

    # 1. Normalize scores
    s1, s2 = _normalize_scores(data)
    if "player1Score" not in data or data.get("player1Score") != s1:
        updates["player1Score"] = s1
    if "player2Score" not in data or data.get("player2Score") != s2:
        updates["player2Score"] = s2

    # 2. Compile participants
    participants = _extract_uids(data)
    if "participants" not in data or data.get("participants") != participants:
        updates["participants"] = participants

    # 3. Determine outcome (winners, losers, winner, etc.)
    outcome = _calculate_outcome(data, s1, s2)
    for key, val in outcome.items():
        if key not in data or data.get(key) != val:
            updates[key] = val

    # 4. Add status if missing
    if "status" not in data:
        updates["status"] = "COMPLETED"

    return updates


def _setup_mock_db() -> Any:
    """Initialize a mock database with test data."""
    from mockfirestore import MockFirestore
    db = MockFirestore()

    # Create users
    u1 = db.collection("users").document("user1")
    u1.set({"displayName": "Alice", "uid": "user1"})
    u2 = db.collection("users").document("user2")
    u2.set({"displayName": "Bob", "uid": "user2"})
    u3 = db.collection("users").document("user3")
    u3.set({"displayName": "Charlie", "uid": "user3"})
    u4 = db.collection("users").document("user4")
    u4.set({"displayName": "David", "uid": "user4"})

    matches_ref = db.collection("matches")

    # 1. Old singles match (deprecated score fields, missing participants)
    matches_ref.document("match1").set({
        "matchType": "singles",
        "player1Ref": u1,
        "player2Ref": u2,
        "player1_score": 11,
        "player2_score": 5,
        "createdAt": datetime.datetime.now(),
    })

    # 2. Old doubles match (legacy format, missing participants)
    matches_ref.document("match2").set({
        "matchType": "doubles",
        "team1": [u1, u2],
        "team2": [u3, u4],
        "player1Score": 8,
        "player2Score": 11,
        "createdAt": datetime.datetime.now(),
    })

    # 3. Already correct match
    matches_ref.document("match3").set({
        "matchType": "singles",
        "player1Ref": u1,
        "player2Ref": u3,
        "player1Score": 11,
        "player2Score": 9,
        "participants": ["user1", "user3"],
        "winner": "team1",
        "winnerId": "user1",
        "loserId": "user3",
        "winners": ["user1"],
        "losers": ["user3"],
        "status": "COMPLETED",
        "createdAt": datetime.datetime.now(),
    })

    return db


if __name__ == "__main__":
    main()
