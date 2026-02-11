"""Tests for the user impersonation feature."""

import unittest
from unittest.mock import MagicMock, patch
from flask import session, g
from pickaladder import create_app

class ImpersonationTestCase(unittest.TestCase):
    """Test case for user impersonation."""

    def setUp(self):
        """Set up a test client and mock environment."""
        self.mock_firestore = patch("pickaladder.firestore.client").start()
        self.mock_firebase_admin = patch("firebase_admin.initialize_app").start()

        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test"})
        print(self.app.url_map)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        self.admin_data = {"name": "Admin", "isAdmin": True, "uid": "admin1", "id": "admin1"}
        self.user_data = {"name": "User", "isAdmin": False, "uid": "user1", "id": "user1"}

        # Setup mock db
        self.db = self.mock_firestore.return_value

    def tearDown(self):
        patch.stopall()
        self.app_context.pop()

    def _mock_user_get(self, user_id, user_data):
        doc_ref = MagicMock()
        doc_snapshot = MagicMock()
        doc_snapshot.exists = True
        doc_snapshot.to_dict.return_value = user_data
        doc_ref.get.return_value = doc_snapshot

        # When db.collection("users").document(user_id).get() is called
        self.db.collection.return_value.document.side_effect = lambda uid: doc_ref if uid == user_id else MagicMock()

    def test_impersonation_flow(self):
        """Test the full impersonation flow: start, verify, stop."""

        # 1. Login as Admin
        with self.client.session_transaction() as sess:
            sess["user_id"] = "admin1"
            sess["is_admin"] = True

        self._mock_user_get("admin1", self.admin_data)

        # 1b. Check if Impersonate button is present in users page
        # Mock search_users to return user1
        with patch("pickaladder.user.services.UserService.search_users") as mock_search:
            mock_search.return_value = [(self.user_data, 'none', 'none')]
            response = self.client.get("/user/users")
            self.assertIn("fa-user-secret", response.data.decode('utf-8'))
            self.assertIn("/admin/impersonate/user1", response.data.decode('utf-8'))

        # 2. Start Impersonation of user1
        # Mock getting user1 data for the redirect flash message
        doc_ref_user1 = MagicMock()
        doc_snapshot_user1 = MagicMock()
        doc_snapshot_user1.exists = True
        doc_snapshot_user1.to_dict.return_value = self.user_data
        doc_ref_user1.get.return_value = doc_snapshot_user1

        # We need to handle both admin1 and user1 lookups
        def document_side_effect(uid):
            if uid == "admin1":
                doc = MagicMock()
                snap = MagicMock()
                snap.exists = True
                snap.to_dict.return_value = self.admin_data
                doc.get.return_value = snap
                return doc
            if uid == "user1":
                return doc_ref_user1
            return MagicMock()

        self.db.collection.return_value.document.side_effect = document_side_effect

        response = self.client.get("/admin/impersonate/user1", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess["impersonate_id"], "user1")

        # 3. Verify g.user is now the impersonated user
        # This is hard to check directly via client.get as it clears g between requests
        # but we can check if the response contains the impersonated user's name or the banner
        data = response.data.decode('utf-8')
        self.assertIn("You are now impersonating User", data)
        self.assertIn("You are impersonating <strong>User</strong>", data)

        # 4. Stop Impersonation
        response = self.client.get("/admin/stop_impersonating", follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as sess:
            self.assertNotIn("impersonate_id", sess)

        self.assertIn(b"Welcome back, Admin", response.data)

    def test_non_admin_cannot_impersonate(self):
        """Ensure non-admins cannot start impersonation."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "user2"
            sess["is_admin"] = False

        response = self.client.get("/admin/impersonate/user1", follow_redirects=True)
        # Should be redirected to dashboard or similar due to admin_required=True
        self.assertIn(b"You are not authorized to view this page", response.data)

        with self.client.session_transaction() as sess:
            self.assertNotIn("impersonate_id", sess)

if __name__ == "__main__":
    unittest.main()
