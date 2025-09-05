from unittest.mock import patch
from tests.helpers import BaseTestCase, TEST_PASSWORD


class AuthTestCase(BaseTestCase):
    def test_login_page_load(self):
        self.create_user(is_admin=True, email="loginpage@example.com")
        response = self.app.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_register_page_load(self):
        self.create_user(is_admin=True, email="registerpage@example.com")
        response = self.app.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Register", response.data)

    @patch("pickaladder.auth.routes.mail.send")
    def test_successful_registration(self, mock_mail_send):
        self.create_user(is_admin=True, email="successfulregistration@example.com")
        response = self.app.post(
            "/auth/register",
            data={
                "username": "newuser",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "email": "new@example.com",
                "name": "New User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Registration successful! Please check your email to verify your account.",
            response.data,
        )
        mock_mail_send.assert_called_once()

    def test_login_logout(self):
        self.create_user(
            username="testuser",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser@example.com",
        )
        # Test successful login
        response = self.login("testuser", TEST_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)
        self.assertIn(b"Logout", response.data)

        # Test successful logout
        response = self.app.get("/auth/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have been logged out.", response.data)
        self.assertIn(b"Login", response.data)

    def test_login_with_invalid_credentials(self):
        self.create_user(
            username="testuser_invalid",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser_invalid@example.com",
        )
        response = self.login("testuser_invalid", "WrongPassword!")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

    def test_access_protected_route_without_login(self):
        self.create_user(is_admin=True, email="protectedroute@example.com")
        response = self.app.get("/user/dashboard", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)
        self.assertIn(b"Please log in to access this page.", response.data)
