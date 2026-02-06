"""Tests for the tournament blast invite route."""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import MagicMock, patch

from mockfirestore import CollectionReference, MockFirestore, Query
from mockfirestore.document import DocumentReference

from pickaladder import create_app
from pickaladder.tournament.services import TournamentService  # noqa: F401
from pickaladder.user.utils import _migrate_ghost_references


# Fix mockfirestore where() to handle FieldFilter
def collection_where(self, field_path=None, op_string=None, value=None, filter=None):
    if filter:
        return self._where(filter.field_path, filter.op_string, filter.value)
    return self._where(field_path, op_string, value)


if not hasattr(CollectionReference, "_where"):
    CollectionReference._where = CollectionReference.where
    CollectionReference.where = collection_where


def query_where(self, field_path=None, op_string=None, value=None, filter=None):
    if filter:
        return self._where(filter.field_path, filter.op_string, filter.value)
    return self._where(field_path, op_string, value)


if not hasattr(Query, "_where"):
    Query._where = Query.where
    Query.where = query_where


# Fix DocumentReference equality
def doc_ref_eq(self, other):
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path


if not hasattr(DocumentReference, "_orig_eq"):
    DocumentReference._orig_eq = DocumentReference.__eq__
    DocumentReference.__eq__ = doc_ref_eq
DocumentReference.__hash__ = lambda self: hash(tuple(self._path))

# Mock user payloads
MOCK_USER_ID = "owner_id"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "owner@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False}


class TournamentBlastTestCase(unittest.TestCase):
    """Test case for the tournament blast invite route."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_db = MockFirestore()

        # Add mock batch support to mockfirestore
        class MockBatch:
            def __init__(self, db):
                self.db = db
                self.updates = []
                self.commit = MagicMock(side_effect=self._real_commit)

            def update(self, ref, data):
                self.updates.append((ref, data))

            def set(self, ref, data, merge=False):
                self.updates.append((ref, data))

            def delete(self, ref):
                pass

            def _real_commit(self):
                for ref, data in self.updates:
                    ref.update(data)

        self.mock_batch_instance = MockBatch(self.mock_db)
        self.mock_db.batch = MagicMock(return_value=self.mock_batch_instance)

        self.mock_firestore_service = MagicMock()
        self.mock_firestore_service.client.return_value = self.mock_db
        self.mock_firestore_service.ArrayUnion = MagicMock(side_effect=lambda x: x)
        self.mock_firestore_service.ArrayRemove = MagicMock(side_effect=lambda x: x)

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

        # Verify ArrayUnion calls
        self.mock_firestore_service.ArrayUnion.assert_called()
        calls = self.mock_firestore_service.ArrayUnion.call_args_list

        # We expect two calls: one for participants, one for participant_ids
        found_participants = False
        found_ids = False
        for call in calls:
            args = call[0][0]
            if not args:
                continue
            if isinstance(args[0], dict) and "userRef" in args[0]:
                self.assertEqual(len(args), 1)
                self.assertEqual(args[0]["email"], "ghost@example.com")
                self.assertEqual(args[0]["userRef"].id, "user_ghost")
                found_participants = True
            elif isinstance(args[0], str):
                self.assertEqual(args, ["user_ghost"])
                found_ids = True

        self.assertTrue(found_participants)
        self.assertTrue(found_ids)

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
