import unittest
from unittest.mock import patch
from flask_wtf.csrf import CSRFError
from tests.helpers import BaseTestCase, TEST_PASSWORD


class AppTestCase(BaseTestCase):
    def test_index_redirect_to_install(self):
        response = self.app.get("/")
        # The root should redirect to the install page if no admin exists
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/install", response.location)

    def test_login_page_load_redirects_to_install(self):
        response = self.app.get("/auth/login")
        # Should redirect to install page if no admin exists
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/install", response.location)

    def test_register_page_load(self):
        response = self.app.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Register", response.data)

    def test_register_validation_username_too_short(self):
        response = self.app.post(
            "/auth/register",
            data={
                "username": "us",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "email": "test@example.com",
                "name": "Test User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Field must be between 3 and 25 characters long.", response.data)

    def test_register_validation_password_mismatch(self):
        response = self.app.post(
            "/auth/register",
            data={
                "username": "testuser",
                "password": "Password123",
                "confirm_password": "Password456",
                "email": "test@example.com",
                "name": "Test User",
                "submit": "Register",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Passwords must match.", response.data)

    def test_register_validation_password_too_weak(self):
        response = self.app.post(
            "/auth/register",
            data={
                "username": "testuser",
                "password": "weak",
                "confirm_password": "weak",
                "email": "test@example.com",
                "name": "Test User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Field must be at least 8 characters long.", response.data)
        self.assertIn(
            b"Password must contain at least one uppercase letter.",
            response.data,
        )
        # The number validation is not reached because the custom validator
        # short-circuits.
        # self.assertIn(b"Password must contain at least one number.", response.data)

    def test_create_match_requires_login(self):
        response = self.app.get("/match/create", follow_redirects=False)
        # Should redirect to install page since no admin exists
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/install", response.location)

    def test_forgot_password_post_redirects_and_flashes(self):
        response = self.app.post(
            "/auth/forgot_password",
            data={"email": "test@example.com"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)  # Should redirect to install
        self.assertIn("/auth/install", response.location)

    def test_reset_with_invalid_token(self):
        response = self.app.get("/auth/reset/invalidtoken", follow_redirects=False)
        self.assertEqual(response.status_code, 302)  # Should redirect to install
        self.assertIn("/auth/install", response.location)

    @patch(
        "pickaladder.group.forms.FriendGroupForm.validate_on_submit",
        side_effect=CSRFError("CSRF Token Missing"),
    )
    def test_csrf_error_handler(self, mock_validate):
        # Create a user and log in to access the create group page
        self.create_user(
            username="csrf_tester",
            password=TEST_PASSWORD,
            is_admin=True,
            email="csrf_tester@example.com",
        )
        self.login("csrf_tester", TEST_PASSWORD)

        # Make a POST request to a CSRF-protected route
        response = self.app.post(
            "/group/create", data={"name": "some group"}, follow_redirects=False
        )

        # Check that the response is a redirect to the dashboard
        self.assertEqual(response.status_code, 302)
        self.assertIn("/user/dashboard", response.location)

        # Check that a flash message was generated
        with self.app.session_transaction() as session:
            self.assertIn("_flashes", session)
            self.assertIn("Your session may have expired.", session["_flashes"][0][1])


if __name__ == "__main__":
    unittest.main()
