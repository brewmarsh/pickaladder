"""Tests for tournament doubles logic."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app

MOCK_USER_ID = "user1"
MOCK_PARTNER_ID = "user2"


class TournamentDoublesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_db = MockFirestore()

        # Patch firestore.client() to return our mock_db
        self.mock_firestore_module = MagicMock()
        self.mock_firestore_module.client.return_value = self.mock_db

        # Mock FieldFilter and other constants
        class MockFieldFilter:
            def __init__(self, field_path: str, op_string: str, value: Any) -> None:
                self.field_path = field_path
                self.op_string = op_string
                self.value = value

        self.mock_firestore_module.FieldFilter = MockFieldFilter
        self.mock_firestore_module.SERVER_TIMESTAMP = "2023-01-01"

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_services": patch(
                "pickaladder.tournament.services.firestore",
                new=self.mock_firestore_module,
            ),
            "firestore_routes": patch(
                "pickaladder.tournament.routes.firestore",
                new=self.mock_firestore_module,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_module
            ),
            "team_service": patch("pickaladder.tournament.services.TeamService"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test_secret",  # nosec B105
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        # Populate mock users
        self.mock_db.collection("users").document(MOCK_USER_ID).set(
            {
                "uid": MOCK_USER_ID,
                "name": "Test User",
                "username": "testuser",
                "email": "user1@example.com",
                "isAdmin": True,
            }
        )
        self.mock_db.collection("users").document(MOCK_PARTNER_ID).set(
            {
                "uid": MOCK_PARTNER_ID,
                "name": "Partner User",
                "username": "partneruser",
                "email": "user2@example.com",
            }
        )

    def _get_auth_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer test-token"}

    def _set_session_user(self, uid: str = MOCK_USER_ID) -> None:
        with self.client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["is_admin"] = False

    def test_register_team_placeholder(self) -> None:
        """Test registering a team with a placeholder partner (invite link)."""
        self._set_session_user()

        tournament_id = "t1"
        team_name = "Team Placeholder"

        # Mock tournament doc
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {"name": "Test Tournament", "mode": "DOUBLES"}
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/register_team",
            data={"team_name": team_name},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invite link generated!", response.data)

        # Verify team document was created
        teams = list(
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .stream()
        )
        self.assertEqual(len(teams), 1)
        team_data = teams[0].to_dict()
        self.assertEqual(team_data["p1_uid"], MOCK_USER_ID)
        self.assertIsNone(team_data["p2_uid"])
        self.assertEqual(team_data["team_name"], team_name)

    def test_claim_team_partnership(self) -> None:
        """Test claiming a placeholder team partnership."""
        self._set_session_user(MOCK_PARTNER_ID)

        tournament_id = "t1"
        team_id = "team_123"

        # Setup tournament and placeholder team
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Test Tournament",
                "mode": "DOUBLES",
                "participant_ids": [MOCK_USER_ID],
                "participants": [
                    {
                        "userRef": self.mock_db.collection("users").document(
                            MOCK_USER_ID
                        ),
                        "status": "accepted",
                    }
                ],
            }
        )
        self.mock_db.collection("tournaments").document(tournament_id).collection(
            "teams"
        ).document(team_id).set(
            {"p1_uid": MOCK_USER_ID, "p2_uid": None, "team_name": "Dynamic Duo"}
        )

        # Mock TeamService
        self.mocks["team_service"].get_or_create_team.return_value = "global_team_abc"

        response = self.client.post(
            f"/tournaments/{tournament_id}/claim_team/{team_id}",
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have joined the team!", response.data)

        # Verify team document was updated
        updated_team = (
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .document(team_id)
            .get()
            .to_dict()
        )
        self.assertEqual(updated_team["p2_uid"], MOCK_PARTNER_ID)
        self.assertEqual(updated_team["status"], "CONFIRMED")
        self.assertEqual(updated_team["team_id"], "global_team_abc")

    def test_generate_bracket_doubles(self) -> None:
        """Test normalized bracket seeding for doubles."""
        from pickaladder.tournament.services import TournamentService

        tournament_id = "t1"

        # Setup tournament mode and confirmed team
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {"mode": "DOUBLES"}
        )
        self.mock_db.collection("tournaments").document(tournament_id).collection(
            "teams"
        ).document("t_team_1").set(
            {
                "team_id": "global_team_1",
                "team_name": "Team Alpha",
                "p1_uid": "u1",
                "p2_uid": "u2",
                "status": "CONFIRMED",
            }
        )

        bracket = TournamentService.generate_bracket(tournament_id, self.mock_db)

        self.assertEqual(len(bracket), 1)
        self.assertEqual(bracket[0]["name"], "Team Alpha")
        self.assertEqual(bracket[0]["type"], "team")
        self.assertEqual(bracket[0]["id"], "global_team_1")
        self.assertIn("u1", bracket[0]["members"])


if __name__ == "__main__":
    unittest.main()
