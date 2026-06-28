"""Tests for application security hardening."""

import unittest

from pickaladder import create_app


class SecurityTestCase(unittest.TestCase):
    """Test case for security-related features."""

    def setUp(self) -> None:
        """Set up a test client with CSRF enabled."""
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": True,
                "SECRET_KEY": "test-secret-key",
            },
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the application context."""
        self.app_context.pop()

    def test_csrf_protection_on_ajax(self) -> None:
        """Verify that POST requests without a CSRF token are rejected."""
        # Log in the user by setting session['user_id']
        # This bypasses the login_required redirect (302)
        with self.client.session_transaction() as sess:
            sess["user_id"] = "test-user"
            sess["is_admin"] = False

        # 1. Test /match/record (JSON)
        # We don't need to mock Firestore for this test because CSRF protection
        # happens before the view function logic that would call Firestore.
        response = self.client.post(
            "/match/record",
            json={
                "match_type": "singles",
                "player1": "user1",
                "player2": "user2",
                "player1_score": 11,
                "player2_score": 5,
            },
        )
        # The app redirects on CSRF error
        assert response.status_code == 302

        # 2. Test /match/challenge/create
        response = self.client.post(
            "/match/challenge/create",
            json={"challenged_id": "other-user", "wager": 10},
        )
        assert response.status_code == 302

    def test_rate_limiting(self) -> None:
        """Verify that rate limiting blocks excessive requests."""
        from pickaladder.core.security import _rate_limit_storage

        self.app.config["TEST_RATE_LIMITING"] = True

        _rate_limit_storage.clear()

        # Log in the user
        with self.client.session_transaction() as sess:
            sess["user_id"] = "test-user"
            sess["is_admin"] = False

        # /match/record is rate limited and supports GET
        for _ in range(5):
            response = self.client.get("/match/record")
            # It might be 200 (if we mock firestore) or it might crash later,
            # but rate limit is hit BEFORE the view logic.
            # However, since we haven't mocked firestore, it might 500.
            # But the rate limiter is BEFORE the view logic.
            # If it's NOT 429, then rate limiting didn't block it yet.
            assert response.status_code != 429

        # 6th request should fail with 429
        response = self.client.get("/match/record")
        assert response.status_code == 429
        assert b"Too many requests" in response.data


if __name__ == "__main__":
    unittest.main()
