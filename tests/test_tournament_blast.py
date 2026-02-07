"""Tests for the tournament blast invite route."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app
from pickaladder.tournament.services import TournamentService  # noqa: F401
from pickaladder.user.services import UserService
from tests.conftest import (
    MockArrayRemove,
    MockArrayUnion,
    MockBatch,
    patch_mockfirestore,
)

patch_mockfirestore()

# Mock user payloads
MOCK_USER_ID = "owner_id"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "owner@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False}


class TournamentBlastTestCase(unittest.TestCase):
    """Test case for the tournament blast invite route."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_db = MockFirestore()

        self.mock_batch_instance = MockBatch(self.mock_db)
        self.mock_db.batch = MagicMock(return_value=self.mock_batch_instance)

        self.mock_firestore_service = MagicMock()
        self.mock_firestore_service.client.return_value = self.mock_db
        self.mock_firestore_service.ArrayUnion = MockArrayUnion
        self.mock_firestore_service.ArrayRemove = MockArrayRemove

        # Mock FieldFilter
        class MockFieldFilter:
            def __init__(self, field_path, op_string, value):
                self.field_path = field_path
                self.op_string = op_string
                self.value = value

        self.mock_firestore_service.FieldFilter = MockFieldFilter

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_services": patch(
                "pickaladder.tournament.services.firestore",
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

    def test_invite_group_success(self) -> None:
        """Test successfully inviting a group to a tournament."""
        self._set_session_user()

        # Setup owner
        owner_ref = self.mock_db.collection("users").document(MOCK_USER_ID)
        owner_ref.set(MOCK_USER_DATA)

        # Setup members
        member1_ref = self.mock_db.collection("users").document("user_real")
        member1_ref.set({"username": "real_user", "is_ghost": False})
        member2_ref = self.mock_db.collection("users").document("user_ghost")
        member2_ref.set(
            {"username": "ghost_123", "is_ghost": True, "email": "ghost@example.com"}
        )

        # Setup group
        group_id = "test_group_id"
        self.mock_db.collection("groups").document(group_id).set(
            {
                "name": "Cool Group",
                "members": [owner_ref, member1_ref, member2_ref],
            }
        )

        # Setup tournament
        tournament_id = "test_tournament_id"
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {
                "name": "Summer Open",
                "organizer_id": MOCK_USER_ID,
                "participant_ids": [MOCK_USER_ID, "user_real"],
                "participants": [
                    {"userRef": owner_ref, "status": "accepted"},
                    {"userRef": member1_ref, "status": "pending"},
                ],
            }
        )

        # Mock standings for the view redirect
        with patch(
            "pickaladder.tournament.services.get_tournament_standings"
        ) as mock_standings:
            mock_standings.return_value = []
            response = self.client.post(
                f"/tournaments/{tournament_id}/invite_group",
                data={"group_id": group_id},
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)

        # Verify batch updates via our MockBatch
        self.mock_db.batch.assert_called()
        self.mock_batch_instance.commit.assert_called()

        # Verify DB update
        t_data = (
            self.mock_db.collection("tournaments")
            .document(tournament_id)
            .get()
            .to_dict()
        )
        self.assertIn("user_ghost", t_data["participant_ids"])
        # Should have 3 participants now: owner, user_real, user_ghost
        self.assertEqual(len(t_data["participants"]), 3)

        # Find ghost participant
        ghost_p = next(
            p for p in t_data["participants"] if p.get("userRef").id == "user_ghost"
        )
        self.assertEqual(ghost_p["status"], "pending")
        self.assertEqual(ghost_p["email"], "ghost@example.com")

    def test_migrate_ghost_references_tournaments(self) -> None:
        """Test that _migrate_ghost_references correctly updates tournaments."""
        mock_db = MagicMock()
        mock_batch = MagicMock()
        ghost_ref = MagicMock()
        ghost_ref.id = "ghost_id"
        real_user_ref = MagicMock()
        real_user_ref.id = "real_id"

        # Mock matches query (singles)
        mock_db.collection.return_value.where.return_value.stream.return_value = []

        # Mock tournament query
        tournament_id = "tourney_123"
        mock_tournament_doc = MagicMock()
        mock_tournament_doc.id = tournament_id
        mock_tournament_doc.reference = MagicMock()
        mock_tournament_doc.to_dict.return_value = {
            "participant_ids": ["ghost_id", "other_id"],
            "participants": [
                {"userRef": ghost_ref, "status": "pending", "email": "g@e.com"},
                {"user_id": "other_id", "status": "accepted"},
            ],
        }

        # Set up the query chain for tournaments
        # _migrate_ghost_references calls
        # db.collection("tournaments").where(...).stream()
        def collection_side_effect(name):
            mock_coll = MagicMock()
            if name == "tournaments":
                mock_coll.where.return_value.stream.return_value = [mock_tournament_doc]
            else:
                mock_coll.where.return_value.stream.return_value = []
            return mock_coll

        mock_db.collection.side_effect = collection_side_effect

        UserService._migrate_ghost_references(
            mock_db, mock_batch, ghost_ref, real_user_ref
        )

        # Verify batch.update was called for the tournament
        mock_batch.update.assert_called()
        # Find the call for the tournament
        tourney_update_call = None
        for call in mock_batch.update.call_args_list:
            if call[0][0] == mock_tournament_doc.reference:
                tourney_update_call = call
                break

        self.assertIsNotNone(tourney_update_call)
        update_data = cast(Any, tourney_update_call)[0][1]

        # Check participant_ids
        self.assertIn("real_id", update_data["participant_ids"])
        self.assertNotIn("ghost_id", update_data["participant_ids"])

        # Check participants
        new_participants = update_data["participants"]
        self.assertEqual(len(new_participants), 2)
        # One should be the real user now
        found_real = False
        for p in new_participants:
            if p.get("userRef") == real_user_ref:
                found_real = True
                self.assertEqual(p.get("user_id"), "real_id")
        self.assertTrue(found_real)


if __name__ == "__main__":
    unittest.main()
