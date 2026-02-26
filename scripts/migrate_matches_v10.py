"""
Migration script to normalize historical match data to the new unified schema.
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
    cred_path = project_root / "firebase_credentials.json"
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
        return False
    bucket = (
        os.environ.get("FIREBASE_STORAGE_BUCKET") or "pickaladder.firebasestorage.app"
    )
    firebase_admin.initialize_app(cred, {"storageBucket": bucket})
    return True


def _get_ids_from_refs(refs: Any) -> list[str]:
    """Extract string IDs from a list of references or strings."""
    if not refs:
        return []
    if not isinstance(refs, list):
        refs = [refs]
    return [str(r.id if hasattr(r, "id") else r) for r in refs if r]


def _extract_uids(data: dict[str, Any]) -> list[str]:
    """Compile a flat list of participant UIDs from various fields."""
    uids: set[str] = set()
    for f in ["player1Ref", "player2Ref", "player1", "player2"]:
        if val := data.get(f):
            uids.add(str(val.id if hasattr(val, "id") else val))

    for f in ["team1", "team2"]:
        uids.update(_get_ids_from_refs(data.get(f)))

    for k in ["player_1_data", "player_2_data"]:
        if isinstance(entry := data.get(k), dict) and (uid := entry.get("uid")):
            uids.add(str(uid))

    if "participants" in data:
        uids.update(_get_ids_from_refs(data["participants"]))
    return sorted(list(uids))


def _normalize_scores(data: dict[str, Any]) -> tuple[int, int]:
    """Normalize scores from various field names."""
    s1 = (
        data.get("player1Score")
        if data.get("player1Score") is not None
        else data.get("player1_score", 0)
    )
    s2 = (
        data.get("player2Score")
        if data.get("player2Score") is not None
        else data.get("player2_score", 0)
    )
    try:
        return int(s1 or 0), int(s2 or 0)
    except (ValueError, TypeError):
        return 0, 0


def _get_sides(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Determine UIDs for side 1 and side 2."""
    if data.get("matchType") == "doubles" or data.get("match_type") == "doubles":
        return _get_ids_from_refs(data.get("team1")), _get_ids_from_refs(
            data.get("team2")
        )

    def get_id(ref_key: str, data_key: str) -> str:
        if ref := data.get(ref_key):
            return str(ref.id if hasattr(ref, "id") else ref)
        if isinstance(entry := data.get(data_key), dict):
            return str(entry.get("uid", ""))
        return ""

    p1, p2 = (
        get_id("player1Ref", "player_1_data"),
        get_id("player2Ref", "player_2_data"),
    )
    return ([p1] if p1 else []), ([p2] if p2 else [])


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
    win1 = s1 > s2
    s1_id = data.get("team1Id") or (side1[0] if side1 else None)
    s2_id = data.get("team2Id") or (side2[0] if side2 else None)
    return {
        "winner": "team1" if win1 else "team2",
        "winnerId": s1_id if win1 else s2_id,
        "loserId": s2_id if win1 else s1_id,
        "winners": side1 if win1 else side2,
        "losers": side2 if win1 else side1,
    }


def _get_match_updates(data: dict[str, Any]) -> dict[str, Any]:
    """Determine necessary updates for a single match document."""
    updates: dict[str, Any] = {}
    s1, s2 = _normalize_scores(data)
    if data.get("player1Score") != s1:
        updates["player1Score"] = s1
    if data.get("player2Score") != s2:
        updates["player2Score"] = s2

    parts = _extract_uids(data)
    if data.get("participants") != parts:
        updates["participants"] = parts

    outcome = _calculate_outcome(data, s1, s2)
    for k, v in outcome.items():
        if data.get(k) != v:
            updates[k] = v
    if "status" not in data:
        updates["status"] = "COMPLETED"
    return updates


def _apply_update(
    doc: Any,
    updates: dict[str, Any],
    dry_run: bool,
    is_mock: bool,
    batch: WriteBatch | None,
) -> bool:
    """Apply updates and return True if committed/batched."""
    if not updates:
        return False
    if dry_run:
        print(f"[DRY] {doc.id}: {updates}")
    elif is_mock:
        doc.reference.update(updates)
    elif batch:
        batch.update(doc.reference, updates)
        return True
    return False


def migrate_matches(db: Any, dry_run: bool = False, batch_size: int = 100) -> None:
    """Main migration loop."""
    is_mock = hasattr(db, "reset") or "MockFirestore" in str(type(db))
    batch: WriteBatch | None = db.batch() if not dry_run and not is_mock else None
    count, total = 0, 0
    for doc in db.collection("matches").stream():
        total += 1
        if _apply_update(
            doc, _get_match_updates(doc.to_dict()), dry_run, is_mock, batch
        ):
            count += 1
            if batch and count % batch_size == 0:
                batch.commit()
                batch = db.batch()
    if batch and count % batch_size != 0:
        batch.commit()
    print(f"\nDone. Processed: {total}, Migrated: {count}")


def _setup_mock_db() -> Any:
    """Set up mock DB for testing."""
    from mockfirestore import MockFirestore

    db = MockFirestore()
    users = []
    for i in range(4):
        u = db.collection("users").document(f"u{i}")
        u.set({"uid": f"u{i}"})
        users.append(u)
    m = db.collection("matches")
    m.document("m1").set(
        {
            "matchType": "singles",
            "player1Ref": users[0],
            "player2Ref": users[1],
            "player1_score": 11,
            "player2_score": 5,
        }
    )
    m.document("m2").set(
        {
            "matchType": "doubles",
            "team1": [users[0], users[1]],
            "team2": [users[2], users[3]],
            "player1Score": 8,
            "player2Score": 11,
        }
    )
    return db


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    if args.mock:
        db = _setup_mock_db()
    else:
        if not initialize_firebase():
            sys.exit(1)
        db = firestore.client()
    migrate_matches(db, args.dry_run, args.batch_size)


if __name__ == "__main__":
    main()
