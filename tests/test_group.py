"""Tests for the group blueprint."""

import unittest
from unittest.mock import MagicMock, patch

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Group Owner", "isAdmin": False}


class GroupRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the group blueprint."""

    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
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

    def tearDown(self):
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self):
        return {"Authorization": "Bearer mock-token"}

    def test_create_group(self):
        """Test successfully creating a new group."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_groups_collection = mock_db.collection("groups")
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_group_id"
        mock_groups_collection.add.return_value = (None, mock_doc_ref)

        mock_group_doc = mock_groups_collection.document("new_group_id")
        mock_group_snapshot = MagicMock()
        mock_group_snapshot.exists = True
        mock_group_snapshot.to_dict.return_value = {
            "name": "My Firebase Group",
            "ownerRef": mock_user_doc,
        }
        mock_group_doc.get.return_value = mock_group_snapshot

        response = self.client.post(
            "/group/create",
            headers=self._get_auth_headers(),
            data={"name": "My Firebase Group"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group created successfully.", response.data)
        mock_groups_collection.add.assert_called_once()
        call_args = mock_groups_collection.add.call_args[0]
        self.assertEqual(call_args[0]["name"], "My Firebase Group")


if __name__ == "__main__":
    unittest.main()
