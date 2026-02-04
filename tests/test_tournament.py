"""Tests for the tournament blueprint."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False}


class TournamentRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the tournament blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.tournament.routes.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
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
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID

        # Add safe defaults for new Firestore calls to avoid mock sorting issues
        mock_user_doc.collection.return_value.stream.return_value = []
        mock_db.collection.return_value.where.return_value.stream.return_value = []
        mock_db.get_all.return_value = []
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_tournaments_collection = mock_db.collection("tournaments")
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_tournament_id"
        mock_tournaments_collection.add.return_value = (None, mock_doc_ref)

        # Mock the document fetch for the redirect
        mock_tournament_doc = mock_tournaments_collection.document.return_value
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Summer Open",
            "date": "2024-06-01",
            "location": "Courtside",
            "matchType": "singles",
            "ownerRef": mock_user_doc,
            "participants": [],
        }
        mock_tournament_doc.get.return_value = mock_tournament_snapshot

        # Mock UserService.get_user_friends
        with patch(
            "pickaladder.tournament.routes.UserService.get_user_friends"
        ) as mock_friends:
            mock_friends.return_value = []

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
        mock_tournaments_collection.add.assert_called_once()
        call_args = mock_tournaments_collection.add.call_args[0]
        self.assertEqual(call_args[0]["name"], "Summer Open")
        self.assertEqual(call_args[0]["matchType"], "singles")
        # Check that it's a datetime object
        self.assertIsInstance(call_args[0]["date"], datetime.datetime)

    def test_edit_tournament(self) -> None:
        """Test successfully editing an existing tournament."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        # Mock tournament doc
        tournament_id = "test_tournament_id"
        mock_tournament_doc = mock_db.collection("tournaments").document(tournament_id)
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Original Name",
            "date": "2024-06-01",
            "location": "Original Location",
            "matchType": "singles",
            "ownerRef": mock_user_doc,
            "organizer_id": MOCK_USER_ID,
        }
        mock_tournament_snapshot.id = tournament_id
        mock_tournament_doc.get.return_value = mock_tournament_snapshot

        # Mock matches query (not ongoing)
        mock_matches_query = mock_db.collection.return_value.where.return_value
        mock_limit_query = mock_matches_query.limit.return_value
        mock_limit_query.stream.return_value = iter([])

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
        self.assertIn(b"Tournament updated successfully.", response.data)
        mock_tournament_doc.update.assert_called_once()
        update_args = mock_tournament_doc.update.call_args[0][0]
        self.assertEqual(update_args["name"], "Updated Name")
        self.assertEqual(update_args["matchType"], "doubles")
        self.assertIsInstance(update_args["date"], datetime.datetime)

    def test_edit_tournament_ongoing(self) -> None:
        """Test that matchType cannot be changed if tournament is ongoing."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        # Mock tournament doc
        tournament_id = "test_tournament_id"
        mock_tournament_doc = mock_db.collection("tournaments").document(tournament_id)
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Original Name",
            "date": "2024-06-01",
            "location": "Original Location",
            "matchType": "singles",
            "ownerRef": mock_user_doc,
            "organizer_id": MOCK_USER_ID,
        }
        mock_tournament_snapshot.id = tournament_id
        mock_tournament_doc.get.return_value = mock_tournament_snapshot

        # Mock matches query (IS ongoing)
        mock_matches_query = mock_db.collection.return_value.where.return_value
        mock_limit_query = mock_matches_query.limit.return_value
        mock_limit_query.stream.return_value = iter([MagicMock()])

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
        mock_tournament_doc.update.assert_called_once()
        update_args = mock_tournament_doc.update.call_args[0][0]
        self.assertEqual(update_args["name"], "Updated Name")
        # matchType should NOT be in update_args or should be the original
        self.assertNotIn("matchType", update_args)

    def test_list_tournaments(self) -> None:
        """Test listing tournaments."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_query = mock_db.collection.return_value.where.return_value
        mock_query.stream.return_value = []  # Empty list for simplicity

        response = self.client.get(
            "/tournaments/",
            headers=self._get_auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournaments", response.data)

    def test_view_tournament_with_invitable_users(self) -> None:
        """Test that only non-participant friends are in the invitable list."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        # Mock tournament doc
        tournament_id = "test_tournament_id"
        mock_tournament_doc = mock_db.collection("tournaments").document(tournament_id)
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_friend_ref = MagicMock()
        mock_friend_ref.id = "friend1"
        mock_participant_ref = MagicMock()
        mock_participant_ref.id = "participant1"

        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Test Tournament",
            "ownerRef": mock_user_doc,
            "participants": [{"userRef": mock_participant_ref, "status": "accepted"}],
            "participant_ids": ["participant1"],
        }
        mock_tournament_snapshot.id = tournament_id
        mock_tournament_doc.get.return_value = mock_tournament_snapshot

        # Mock friends: one who is already a participant, one who is not
        friends_data = [
            {"id": "friend1", "username": "Friend One", "name": "Friend One"},
            {
                "id": "participant1",
                "username": "Participant One",
                "name": "Participant One",
            },
        ]

        # Mock friends sub-collection
        mock_friends_query = mock_user_doc.collection.return_value.stream
        mock_friend_doc = MagicMock()
        mock_friend_doc.id = "friend1"
        mock_friends_query.return_value = [mock_friend_doc]

        # Mock groups query
        mock_groups_query = mock_db.collection.return_value.where.return_value.stream
        mock_groups_query.return_value = []

        # Mock db.get_all
        def mock_get_all(refs):
            results = []
            for ref in refs:
                doc = MagicMock()
                doc.exists = True
                doc.id = ref.id
                if ref.id == "friend1":
                    doc.to_dict.return_value = {"username": "Friend One", "name": "Friend One"}
                elif ref.id == "participant1":
                    doc.to_dict.return_value = {"username": "Participant One", "name": "Participant One"}
                else:
                    doc.to_dict.return_value = {"username": ref.id, "name": ref.id}
                results.append(doc)
            return results

        mock_db.get_all.side_effect = mock_get_all

        with (
            patch(
                "pickaladder.tournament.routes.get_tournament_standings"
            ) as mock_standings,
        ):
            mock_standings.return_value = []

            response = self.client.get(
                f"/tournaments/{tournament_id}",
                headers=self._get_auth_headers(),
            )

        self.assertEqual(response.status_code, 200)
        # Check that Friend One is in the options but Participant One is not
        self.assertIn(b"Friend One", response.data)
        # Note: Participant One's name might appear in the participant list,
        # but we want to check the select options.
        # But wait, the name "Participant One" WILL appear because they
        # are a participant.
        # However, it should NOT appear as an OPTION in the select field.
        # WTForms renders options as <option value="id">label</option>
        self.assertIn(b'<option value="friend1">Friend One</option>', response.data)
        self.assertNotIn(
            b'<option value="participant1">Participant One</option>', response.data
        )


if __name__ == "__main__":
    unittest.main()
