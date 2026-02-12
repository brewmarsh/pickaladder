"""Tests for tournament doubles logic."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

MOCK_USER_ID = "user1"
MOCK_PARTNER_ID = "user2"

class TournamentDoublesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        """Set up a test client and mock the necessary Firebase services."""
        self.mock_firestore_service = MagicMock()
        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.tournament.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_utils": patch(
                "pickaladder.tournament.utils.firestore", new=self.mock_firestore_service
            ),
            "firestore_service": patch(
                "pickaladder.tournament.services.firestore", new=self.mock_firestore_service
            ),
            "team_service": patch("pickaladder.teams.services.TeamService"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test_secret",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self.mock_db = self.mock_firestore_service.client.return_value

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
        mock_t_ref = self.mock_db.collection.return_value.document.return_value

        # Mock teams sub-collection add
        mock_teams_coll = mock_t_ref.collection.return_value
        mock_new_team_ref = mock_teams_coll.document.return_value
        mock_new_team_ref.id = "team_123"

        response = self.client.post(
            f"/tournaments/{tournament_id}/register_team",
            data={"team_name": team_name},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invite link generated!", response.data)

        # Verify set was called with None partner
        call_args = mock_new_team_ref.set.call_args[0][0]
        self.assertEqual(call_args["p1_uid"], MOCK_USER_ID)
        self.assertIsNone(call_args["p2_uid"])
        self.assertEqual(call_args["team_name"], team_name)

    def test_claim_team_partnership(self) -> None:
        """Test claiming a placeholder team partnership."""
        self._set_session_user(MOCK_PARTNER_ID)

        tournament_id = "t1"
        team_id = "team_123"

        # Mock team data
        mock_t_ref = self.mock_db.collection.return_value.document.return_value
        mock_team_ref = mock_t_ref.collection.return_value.document.return_value
        mock_team_snap = mock_team_ref.get.return_value
        mock_team_snap.exists = True
        mock_team_snap.to_dict.return_value = {
            "p1_uid": MOCK_USER_ID,
            "p2_uid": None,
            "team_name": "Dynamic Duo"
        }

        # Mock tournament data
        mock_t_snap = mock_t_ref.get.return_value
        mock_t_snap.to_dict.return_value = {
            "participant_ids": [MOCK_USER_ID],
            "participants": []
        }

        # Mock TeamService
        self.mocks["team_service"].get_or_create_team.return_value = "global_team_abc"

        response = self.client.post(
            f"/tournaments/{tournament_id}/claim_team/{team_id}",
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have joined the team!", response.data)

        # Verify team update
        mock_team_ref.update.assert_called_with({
            "p2_uid": MOCK_PARTNER_ID,
            "status": "CONFIRMED",
            "team_id": "global_team_abc"
        })

    def test_generate_bracket_doubles(self) -> None:
        """Test normalized bracket seeding for doubles."""
        from pickaladder.tournament.services import TournamentService

        tournament_id = "t1"

        # Mock tournament mode
        mock_t_ref = self.mock_db.collection.return_value.document.return_value
        mock_t_snap = mock_t_ref.get.return_value
        mock_t_snap.exists = True
        mock_t_snap.to_dict.return_value = {"mode": "DOUBLES"}

        # Mock teams sub-collection query
        mock_teams_query = mock_t_ref.collection.return_value.where.return_value
        mock_team_doc = MagicMock()
        mock_team_doc.id = "t_team_1"
        mock_team_doc.to_dict.return_value = {
            "team_id": "global_team_1",
            "team_name": "Team Alpha",
            "p1_uid": "u1",
            "p2_uid": "u2",
            "status": "CONFIRMED"
        }
        mock_teams_query.stream.return_value = [mock_team_doc]

        bracket = TournamentService.generate_bracket(tournament_id, self.mock_db)

        self.assertEqual(len(bracket), 1)
        self.assertEqual(bracket[0]["name"], "Team Alpha")
        self.assertEqual(bracket[0]["type"], "team")
        self.assertEqual(bracket[0]["id"], "global_team_1")
        self.assertIn("u1", bracket[0]["members"])

if __name__ == "__main__":
    unittest.main()
