"""
This script migrates existing doubles matches to use the new Team data model.

- Scans all 'doubles' matches.
- For each team in a match, it creates a corresponding Team document if one
  doesn't already exist. A team is uniquely identified by the sorted IDs of its members.
- Updates the Match document with 'team1Ref' and 'team2Ref' pointing to the
  new Team documents.
- Includes a verification step at the end to confirm the migration.
"""

import json
import os
import sys
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore
from mockfirestore import MockFirestore

from pickaladder.teams.models import create_team_document

# Add the project root to the Python path to allow importing 'pickaladder'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


TEAM_SIZE = 2


def initialize_firebase():
    """Initializes the Firebase Admin SDK."""
    cred = None
    # Try loading from file (for local dev)
    cred_path = project_root / "firebase_credentials.json"
    if cred_path.exists():
        try:
            cred = credentials.Certificate(str(cred_path))
        except Exception as e:
            print(f"Error loading credentials from file: {e}")
            return False
    else:
        # Fallback to environment variable (for production/CI)
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                cred_info = json.loads(cred_json)
                cred = credentials.Certificate(cred_info)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing FIREBASE_CREDENTIALS_JSON: {e}")
                return False

    if not cred:
        print("Could not find Firebase credentials in file or environment variable.")
        return False

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return True


def get_or_create_team(db, team_members):
    """
    Retrieves a team if it exists, otherwise creates it.
    A team is uniquely identified by its members.
    """
    if not team_members or len(team_members) != TEAM_SIZE:
        return None

    sorted_member_ids = sorted([ref.id for ref in team_members])

    # Query for an existing team with the same members
    teams_ref = db.collection("teams")
    query = teams_ref.where("member_ids", "==", sorted_member_ids)
    docs = list(query.stream())

    if docs:
        # Team already exists
        return docs[0].reference
    else:
        # Team does not exist, create it
        print(f"Creating new team for members: {sorted_member_ids}")
        return create_team_document(db, team_members)


def migrate_matches_to_teams():
    """Main migration logic."""
    if os.environ.get("MOCK_DB"):
        db = MockFirestore()
        # Populate with some test data
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
                "matchType": "singles",  # Should be ignored
                "player1Ref": user1_ref,
                "player2Ref": user3_ref,
            }
        )

    else:
        if not initialize_firebase():
            return
        db = firestore.client()

    matches_ref = db.collection("matches")
    doubles_matches_query = matches_ref.where("matchType", "==", "doubles")
    doubles_matches = list(doubles_matches_query.stream())

    if not doubles_matches:
        print("No doubles matches found to migrate.")
        return

    print(f"Found {len(doubles_matches)} doubles matches to process.")
    migrated_match_id = None

    for match in doubles_matches:
        match_data = match.to_dict()
        match_id = match.id

        # Skip if already migrated
        if "team1Ref" in match_data and "team2Ref" in match_data:
            continue

        print(f"Processing match {match_id}...")

        team1_members = match_data.get("team1")
        team2_members = match_data.get("team2")

        team1_ref = get_or_create_team(db, team1_members)
        team2_ref = get_or_create_team(db, team2_members)

        if team1_ref and team2_ref:
            match.reference.update({"team1Ref": team1_ref, "team2Ref": team2_ref})
            print(f"Successfully updated match {match_id}.")
            if not migrated_match_id:
                migrated_match_id = match_id
        else:
            print(f"Skipping match {match_id} due to missing team data.")

    print("\nMigration complete.")

    # --- Verification Step ---
    if migrated_match_id:
        print("\n--- Verifying Migration ---")
        verify_migration(db, migrated_match_id)
    else:
        print("\n--- No new matches were migrated, skipping verification ---")


def verify_migration(db, match_id):
    """Fetches one migrated match and its team to verify the changes."""
    print(f"Verifying match with ID: {match_id}")
    match_ref = db.collection("matches").document(match_id)
    match_doc = match_ref.get()

    if not match_doc.exists:
        print("Verification failed: Migrated match not found.")
        return

    match_data = match_doc.to_dict()
    print("\n--- Migrated Match Data ---")
    print(match_data)

    team1_ref = match_data.get("team1Ref")
    if not team1_ref:
        print("\nVerification failed: 'team1Ref' is missing.")
        return

    team_doc = team1_ref.get()
    if not team_doc.exists:
        print(
            "\nVerification failed: Team document pointed to by 'team1Ref' not found."
        )
        return

    team_data = team_doc.to_dict()
    print("\n--- Corresponding Team Data ---")
    print(team_data)
    print("\n--- Verification Successful ---")


if __name__ == "__main__":
    migrate_matches_to_teams()
