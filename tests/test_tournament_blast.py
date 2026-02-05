"""Tests for the tournament blast invite route."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.user.utils import _migrate_ghost_references

# Mock user payloads
MOCK_USER_ID = "owner_id"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "owner@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False}


class TournamentBlastTestCase(unittest.TestCase):
    """Test case for the tournament blast invite route."""

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

    def test_invite_group_success(self) -> None:
        """Test successfully inviting a group to a tournament."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Use a dictionary to map collection names and document IDs to mocks
        collection_mocks = {}

        def get_collection(name):
            if name not in collection_mocks:
                mock_coll = MagicMock()
                collection_mocks[name] = mock_coll
                doc_mocks = {}

                def get_document(doc_id):
                    if doc_id not in doc_mocks:
                        mock_doc = MagicMock()
                        mock_doc.id = doc_id
                        mock_doc.reference = mock_doc
                        doc_mocks[doc_id] = mock_doc
                    return doc_mocks[doc_id]

                mock_coll.document.side_effect = get_document
            return collection_mocks[name]

        mock_db.collection.side_effect = get_collection

        # Mock owner user doc
        mock_owner_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_owner_snapshot = MagicMock()
        mock_owner_snapshot.exists = True
        mock_owner_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_owner_doc.get.return_value = mock_owner_snapshot

        # Mock group
        group_id = "test_group_id"
        mock_group_ref = mock_db.collection("groups").document(group_id)
        mock_group_snapshot = MagicMock()
        mock_group_snapshot.exists = True

        member1_ref = mock_db.collection("users").document("user_real")
        member2_ref = mock_db.collection("users").document("user_ghost")

        mock_group_snapshot.to_dict.return_value = {
            "name": "Cool Group",
            "members": [member1_ref, member2_ref],
        }
        mock_group_ref.get.return_value = mock_group_snapshot

        # Mock tournament
        tournament_id = "test_tournament_id"
        mock_tournament_ref = mock_db.collection("tournaments").document(tournament_id)
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Summer Open",
            "participant_ids": ["owner_id", "user_real"],
            "participants": [
                {"userRef": mock_owner_doc, "status": "accepted"},
                {"userRef": member1_ref, "status": "pending"},
            ],
        }
        mock_tournament_ref.get.return_value = mock_tournament_snapshot

        # Mock member docs for db.get_all
        member1_doc = MagicMock()
        member1_doc.exists = True
        member1_doc.id = "user_real"
        member1_doc.to_dict.return_value = {"username": "real_user", "is_ghost": False}
        member1_doc.reference = member1_ref

        member2_doc = MagicMock()
        member2_doc.exists = True
        member2_doc.id = "user_ghost"
        member2_doc.to_dict.return_value = {
            "username": "ghost_123",
            "is_ghost": True,
            "email": "ghost@example.com",
        }
        member2_doc.reference = member2_ref

        mock_db.get_all.return_value = [member1_doc, member2_doc]

        # Mock batch
        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        # Mock standings for the view redirect (follow_redirects=False is easier)
        response = self.client.post(
            f"/tournaments/{tournament_id}/invite_group",
            data={"group_id": group_id},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        # Verify batch updates
        mock_db.batch.assert_called_once()
        mock_batch.update.assert_called_once()

        # Should only invite member2 (ghost) because member1 already a participant
        # In this environment, firestore is mocked, so ArrayUnion is a mock.
        self.mock_firestore_service.ArrayUnion.assert_called()

        # Find call for participants
        # It's called twice, once for participants and once for participant_ids
        calls = self.mock_firestore_service.ArrayUnion.call_args_list

        # Verify participant object
        invited_p_list = calls[0][0][0]
        self.assertEqual(len(invited_p_list), 1)
        self.assertEqual(invited_p_list[0]["email"], "ghost@example.com")
        self.assertEqual(invited_p_list[0]["userRef"], member2_ref)

        # Verify participant_ids
        invited_ids_list = calls[1][0][0]
        self.assertEqual(invited_ids_list, ["user_ghost"])

        mock_batch.commit.assert_called_once()

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

        _migrate_ghost_references(mock_db, mock_batch, ghost_ref, real_user_ref)

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
