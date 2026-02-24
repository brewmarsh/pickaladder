"""
This script migrates existing doubles matches to use the new Team data model.

- Scans all 'doubles' matches.
- For each team in a match, it creates a corresponding Team document if one
  doesn't already exist. A team is uniquely identified by the sorted IDs of its members.
- Updates the Match document with 'team1Ref' and 'team2Ref' pointing to the
  new Team documents.
- Includes a verification step at the end to confirm the migration.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
from mockfirestore import MockFirestore

from pickaladder.teams.models import create_team_document

# Add the project root to the Python path to allow importing 'pickaladder'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


TEAM_SIZE = 2


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


def _load_credentials_from_file(cred_path: Path) -> credentials.Certificate | None:
    """Load Firebase credentials from a JSON file."""
    if not cred_path.exists():
        return None
    return _load_certificate(str(cred_path))


def _parse_cred_json(cred_json: str) -> credentials.Certificate | None:
    """Parse JSON string and load certificate."""
    try:
        return _load_certificate(json.loads(cred_json))
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing FIREBASE_CREDENTIALS_JSON: {e}")
        return None


def _load_credentials_from_env() -> credentials.Certificate | None:
    """Load Firebase credentials from an environment variable."""
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if not cred_json:
        return None
    return _parse_cred_json(cred_json)


def _load_credentials() -> credentials.Certificate | None:
    """Load Firebase credentials from file or environment variable."""
    cred = (
        _load_credentials_from_file(_get_credentials_path())
        or _load_credentials_from_env()
    )
    if not cred:
        print("Could not find Firebase credentials in file or environment variable.")
    return cred


def initialize_firebase() -> bool:
    """Initializes the Firebase Admin SDK."""
    cred = _load_credentials()
    if not cred:
        return False

    if not firebase_admin._apps:
        bucket = (
            os.environ.get("FIREBASE_STORAGE_BUCKET")
            or "pickaladder.firebasestorage.app"
        )
        firebase_admin.initialize_app(cred, {"storageBucket": bucket})
    return True


def get_or_create_team(db: Any, team_members: list[Any] | None) -> Any:
    """
    Retrieves a team if it exists, otherwise creates it.
    A team is uniquely identified by its members.
    """
    if not team_members or len(team_members) != TEAM_SIZE:
        return None

    sorted_member_ids = sorted([ref.id for ref in team_members])

    teams_ref = db.collection("teams")
    docs = list(teams_ref.where("member_ids", "==", sorted_member_ids).stream())

    if docs:
        return docs[0].reference
    print(f"Creating new team for members: {sorted_member_ids}")
    return create_team_document(db, team_members)


def _setup_mock_db() -> MockFirestore:
    """Initialize a mock database with test data."""
    db = MockFirestore()
    user1_ref = db.collection("users").document("user1")
    user1_ref.set({"name": "Player A"})
    user2_ref = db.collection("users").document("user2")
    user2_ref.set({"name": "Player B"})
    user3_ref = db.collection("users").document("user3")
    user3_ref.set({"name": "Player C"})
    user4_ref = db.collection("users").document("user4")
    user4_ref.set({"name": "Player D"})

    matches_ref = db.collection("matches")
    matches_ref.add(
        {
            "matchType": "doubles",
            "team1": [user1_ref, user2_ref],
            "team2": [user3_ref, user4_ref],
            "player1Score": 11,
            "player2Score": 8,
        }
    )
    matches_ref.add(
        {
            "matchType": "singles",
            "player1Ref": user1_ref,
            "player2Ref": user3_ref,
        }
    )
    return db


def _migrate_match(match: Any, db: Any) -> bool:
    """Migrate a single match and return True if successful."""
    data = match.to_dict()
    if "team1Ref" in data and "team2Ref" in data:
        return False

    print(f"Processing match {match.id}...")
    t1_ref = get_or_create_team(db, data.get("team1"))
    t2_ref = get_or_create_team(db, data.get("team2"))

    if t1_ref and t2_ref:
        match.reference.update({"team1Ref": t1_ref, "team2Ref": t2_ref})
        print(f"Successfully updated match {match.id}.")
        return True

    print(f"Skipping match {match.id} due to missing team data.")
    return False


def _process_matches_migration(db: Any, matches: list[Any]) -> str | None:
    """Iterate through doubles matches and update them with team references."""
    migrated_match_id = None
    for match in matches:
        if _migrate_match(match, db) and not migrated_match_id:
            migrated_match_id = match.id
    return migrated_match_id


def _get_db() -> Any | None:
    """Setup and return Firestore client or Mock Firestore."""
    if os.environ.get("MOCK_DB"):
        return _setup_mock_db()
    if initialize_firebase():
        return firestore.client()
    return None


def _perform_verification(db: Any, migrated_id: str | None) -> None:
    """Helper to trigger verification if migration occurred."""
    if migrated_id:
        print("\n--- Verifying Migration ---")
        verify_migration(db, migrated_id)


def migrate_matches_to_teams() -> None:
    """Main migration logic."""
    db = _get_db()
    if db is None:
        return

    stream = db.collection("matches").where("matchType", "==", "doubles").stream()
    doubles_matches = list(stream)

    if not doubles_matches:
        print("No doubles matches found to migrate.")
        return

    print(f"Found {len(doubles_matches)} doubles matches to process.")
    migrated_id = _process_matches_migration(db, doubles_matches)

    print("\nMigration complete.")
    _perform_verification(db, migrated_id)


def verify_migration(db: Any, match_id: str) -> None:
    """Fetches one migrated match and its team to verify the changes."""
    print(f"Verifying match with ID: {match_id}")
    match_doc = db.collection("matches").document(match_id).get()

    if not match_doc.exists:
        print("Verification failed: Migrated match not found.")
        return

    match_data = match_doc.to_dict()
    print("\n--- Migrated Match Data ---\n", match_data)

    team1_ref = match_data.get("team1Ref")
    if not team1_ref or not team1_ref.get().exists:
        print("\nVerification failed: 'team1Ref' missing or invalid.")
        return

    print("\n--- Corresponding Team Data ---\n", team1_ref.get().to_dict())
    print("\n--- Verification Successful ---")


if __name__ == "__main__":
    migrate_matches_to_teams()
