import unittest
from unittest.mock import patch, MagicMock

# Pre-emptive imports to ensure patch targets exist.

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Group Owner", "isAdmin": False}


class GroupRoutesFirebaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            # Patch for the `before_request` user loader in `__init__.py`.
            "init_firebase_admin": patch("pickaladder.firebase_admin"),
            "init_firestore": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            # Patch for the group routes.
            "group_routes_firestore": patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
            ),
            # Patch for the login route, which can be a redirect target.
            "auth_routes_firestore": patch(
                "pickaladder.auth.routes.firestore", new=self.mock_firestore_service
            ),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.mocks["init_firebase_admin"].auth = self.mock_auth_service

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()

    def _simulate_login(self):
        """Configure mocks for a logged-in user."""
        self.mock_auth_service.verify_id_token.return_value = MOCK_USER_PAYLOAD

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)

        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_doc_snapshot

        # Mock the admin check in the login route to prevent redirects to /install.
        mock_db.collection(
            "users"
        ).where.return_value.limit.return_value.get.return_value = [MagicMock()]

        return {"Authorization": "Bearer mock-token"}

    def test_create_group(self):
        """Test successfully creating a new group."""
        headers = self._simulate_login()

        # Mock the `add` method on the groups collection
        mock_groups_collection = (
            self.mock_firestore_service.client.return_value.collection("groups")
        )

        # `add` returns a tuple: (timestamp, document_reference)
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_group_id"
        mock_groups_collection.add.return_value = (None, mock_doc_ref)

        # The view_group route will be called, so we need to mock its Firestore calls as well.
        mock_group_doc = MagicMock()
        mock_group_snapshot = MagicMock()
        mock_group_snapshot.exists = True
        # The group data needs an ownerRef for the template to render correctly.
        mock_owner_ref = self.mock_firestore_service.client.return_value.collection(
            "users"
        ).document(MOCK_USER_ID)
        mock_group_snapshot.to_dict.return_value = {
            "name": "My Firebase Group",
            "ownerRef": mock_owner_ref,
        }
        mock_group_doc.get.return_value = mock_group_snapshot
        mock_groups_collection.document.return_value = mock_group_doc

        # The view_group route also fetches the owner's data.
        mock_owner_snapshot = MagicMock()
        mock_owner_snapshot.exists = True
        mock_owner_snapshot.to_dict.return_value = {"username": "Group Owner"}
        mock_owner_ref.get.return_value = mock_owner_snapshot

        response = self.client.post(
            "/group/create",
            headers=headers,
            data={"name": "My Firebase Group"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group created successfully.", response.data)
        mock_groups_collection.add.assert_called_once()

        # We can also check that the data passed to the `add` method was correct.
        # The first element of the first call's arguments is the data dictionary.
        call_args = mock_groups_collection.add.call_args[0]
        self.assertEqual(call_args[0]["name"], "My Firebase Group")


if __name__ == "__main__":
    unittest.main()
