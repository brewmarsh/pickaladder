"""Tests for the tournament blueprint using mockfirestore."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from mockfirestore import CollectionReference, MockFirestore, Query
from mockfirestore.document import DocumentReference

from pickaladder import create_app


# Fix mockfirestore where() to handle FieldFilter
def collection_where(self, field_path=None, op_string=None, value=None, filter=None):
    if filter:
        return self._where(filter.field_path, filter.op_string, filter.value)
    return self._where(field_path, op_string, value)


CollectionReference._where = CollectionReference.where
CollectionReference.where = collection_where


def query_where(self, field_path=None, op_string=None, value=None, filter=None):
    if filter:
        return self._where(filter.field_path, filter.op_string, filter.value)
    return self._where(field_path, op_string, value)


Query._where = Query.where
Query.where = query_where


# Fix DocumentReference equality
def doc_ref_eq(self, other):
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path


DocumentReference.__eq__ = doc_ref_eq
DocumentReference.__hash__ = lambda self: hash(tuple(self._path))

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False, "username": "user1"}


class TournamentRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the tournament blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_db = MockFirestore()

        # Add missing batch method to mock-firestore
        def mock_batch():
            batch = MagicMock()
            batch.update.side_effect = lambda ref, data: ref.update(data)
            return batch

        self.mock_db.batch = MagicMock(side_effect=mock_batch)

        # Patch firestore.client() to return our mock_db
        self.mock_firestore_module = MagicMock()
        self.mock_firestore_module.client.return_value = self.mock_db

        # Mock FieldFilter and other constants
        class MockFieldFilter:
            def __init__(self, field_path, op_string, value):
                self.field_path = field_path
                self.op_string = op_string
                self.value = value

        self.mock_firestore_module.FieldFilter = MockFieldFilter
        self.mock_firestore_module.ArrayUnion = lambda x: x
        self.mock_firestore_module.ArrayRemove = lambda x: x
        self.mock_firestore_module.SERVER_TIMESTAMP = "2023-01-01"

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.tournament.routes.firestore",
                new=self.mock_firestore_module,
            ),
            "firestore_services": patch(
                "pickaladder.tournament.services.firestore",
                new=self.mock_firestore_module,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_module
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Setup current user in mock DB
        self.mock_db.collection("users").document(MOCK_USER_ID).set(MOCK_USER_DATA)

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        """Set a logged-in user in the session."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self) -> dict[str, str]:
        """Get standard authentication headers for tests."""
        return {"Authorization": "Bearer mock-token"}

    def test_create_tournament(self) -> None:
        """Test successfully creating a new tournament."""
        self._set_session_user()

        response = self.client.post(
            "/tournaments/create",
            headers=self._get_auth_headers(),
            data={
                "name": "Summer Open",
                "date": "2024-06-01",
                "location": "Courtside",
                "match_type": "singles",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournament created successfully.", response.data)

        # Verify it exists in DB
        tournaments = list(self.mock_db.collection("tournaments").stream())
        self.assertEqual(len(tournaments), 1)
        data = tournaments[0].to_dict()
        self.assertEqual(data["name"], "Summer Open")
        self.assertEqual(data["matchType"], "singles")

    def test_edit_tournament(self) -> None:
        """Test successfully editing an existing tournament."""
        self._set_session_user()

        # Setup existing tournament
        tournament_id = "test_tournament_id"
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Original Name",
                "date": datetime.datetime(2024, 6, 1),
                "location": "Original Location",
                "matchType": "singles",
                "ownerRef": user_ref,
                "organizer_id": MOCK_USER_ID,
            }
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/edit",
            headers=self._get_auth_headers(),
            data={
                "name": "Updated Name",
                "date": "2024-07-01",
                "location": "Updated Location",
                "match_type": "doubles",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Updated!", response.data)

        # Verify update in DB
        data = (
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .get()
            .to_dict()
        )
        self.assertEqual(data["name"], "Updated Name")
        self.assertEqual(data["matchType"], "doubles")

    def test_edit_tournament_ongoing(self) -> None:
        """Test that matchType cannot be changed if tournament is ongoing."""
        self._set_session_user()

        # Setup existing tournament
        tournament_id = "test_tournament_id"
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Original Name",
                "date": datetime.datetime(2024, 6, 1),
                "location": "Original Location",
                "matchType": "singles",
                "ownerRef": user_ref,
                "organizer_id": MOCK_USER_ID,
            }
        )

        # Setup an ongoing match for this tournament
        self.mock_db.collection("matches").add({"tournamentId": tournament_id})

        response = self.client.post(
            f"/tournaments/{tournament_id}/edit",
            headers=self._get_auth_headers(),
            data={
                "name": "Updated Name",
                "date": "2024-07-01",
                "location": "Updated Location",
                "match_type": "doubles",  # Attempt to change matchType
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Updated!", response.data)

        # Verify that matchType was NOT updated
        data = (
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .get()
            .to_dict()
        )
        self.assertEqual(data["name"], "Updated Name")
        self.assertEqual(data["matchType"], "singles")  # Should still be singles

    def test_list_tournaments(self) -> None:
        """Test listing tournaments."""
        self._set_session_user()
        response = self.client.get(
            "/tournaments/",
            headers=self._get_auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournaments", response.data)

    def test_view_tournament_with_invitable_users(self) -> None:
        """Test that only non-participant players are in the invitable list."""
        self._set_session_user()

        tournament_id = "test_tournament_id"
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)
        participant1_ref = self.mock_db.collection("users").document("participant1")
        participant1_ref.set({"username": "Participant One", "name": "Participant One"})

        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Test Tournament",
                "ownerRef": user_ref,
                "participants": [{"userRef": participant1_ref, "status": "accepted"}],
                "participant_ids": ["participant1"],
                "date": datetime.datetime(2024, 6, 1),
            }
        )

        # Friend (Accepted)
        self.mock_db.collection("users").document("friend1").set(
            {"username": "Friend One", "name": "Friend One"}
        )
        user_ref.collection("friends").document("friend1").set({"status": "accepted"})

        # Group Member
        self.mock_db.collection("users").document("group_member1").set(
            {"username": "Group Member", "name": "Group Member"}
        )
        self.mock_db.collection("groups").add(
            {
                "members": [
                    user_ref,
                    self.mock_db.collection("users").document("group_member1"),
                ],
                "name": "Test Group",
            }
        )

        with patch(
            "pickaladder.tournament.services.get_tournament_standings"
        ) as mock_standings:
            mock_standings.return_value = []

            response = self.client.get(
                f"/tournaments/{tournament_id}",
                headers=self._get_auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend One", response.data)
        self.assertIn(b"Group Member", response.data)

        # Check select options
        self.assertIn(b'<option value="friend1">Friend One</option>', response.data)
        self.assertIn(
            b'<option value="group_member1">Group Member</option>', response.data
        )
        self.assertNotIn(
            b'<option value="participant1">Participant One</option>', response.data
        )

    def test_invite_group(self) -> None:
        """Test inviting all members of a group to a tournament."""
        self._set_session_user()

        tournament_id = "test_tournament_id"
        group_id = "test_group_id"
        user_ref = self.mock_db.collection("users").document(MOCK_USER_ID)
        member2_ref = self.mock_db.collection("users").document("member2")
        member2_ref.set({"name": "Member Two"})

        # Setup tournament
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Test Tournament",
                "organizer_id": MOCK_USER_ID,
                "participant_ids": [MOCK_USER_ID],
            }
        )

        # Setup group
        self.mock_db.collection("groups").document(group_id).set(
            {"name": "Test Group", "members": [user_ref, member2_ref]}
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/invite_group",
            headers=self._get_auth_headers(),
            data={"group_id": group_id},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invited 1 members from the group.", response.data)

        # Verify DB update
        data = (
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .get()
            .to_dict()
        )
        self.assertIn("member2", data["participant_ids"])
        # Check that owner (MOCK_USER_ID) was not re-invited
        # Since owner was already in participant_ids, they should be filtered out.

    def test_invite_group_not_owner(self) -> None:
        """Test that non-owners cannot invite groups."""
        self._set_session_user()

        tournament_id = "test_tournament_id"
        group_id = "test_group_id"

        # Setup tournament with different owner
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Test Tournament",
                "organizer_id": "other_user",
                "participant_ids": ["other_user"],
            }
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/invite_group",
            headers=self._get_auth_headers(),
            data={"group_id": group_id},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Unauthorized.", response.data)

    def test_invite_group_not_member(self) -> None:
        """Test that user cannot invite from a group they don't belong to."""
        self._set_session_user()

        tournament_id = "test_tournament_id"
        group_id = "test_group_id"
        other_user_ref = self.mock_db.collection("users").document("other_user")

        # Setup tournament
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Test Tournament",
                "organizer_id": MOCK_USER_ID,
                "participant_ids": [MOCK_USER_ID],
            }
        )

        # Setup group user is NOT in
        self.mock_db.collection("groups").document(group_id).set(
            {"name": "Test Group", "members": [other_user_ref]}
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/invite_group",
            headers=self._get_auth_headers(),
            data={"group_id": group_id},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"You can only invite members from groups you belong to.", response.data
        )


if __name__ == "__main__":
    unittest.main()
