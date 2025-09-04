from tests.helpers import BaseTestCase, create_user, TEST_PASSWORD
from unittest.mock import patch


class AuthTestCase(BaseTestCase):
    def test_login_page_load(self):
        create_user(is_admin=True, email="loginpage@example.com")
        response = self.app.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_register_page_load(self):
        create_user(is_admin=True, email="registerpage@example.com")
        response = self.app.get("/auth/register")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Register", response.data)

    def test_successful_registration(self):
        create_user(is_admin=True, email="successfulregistration@example.com")
        response = self.app.post(
            "/auth/register",
            data={
                "username": "newuser",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "email": "new@example.com",
                "name": "New User",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        response = self.app.get(response.location)
        self.assertIn(b"Registration successful", response.data)

    def test_login_logout(self):
        create_user(
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
        with self.app as c:
            response = c.get("/auth/logout")
            self.assertEqual(response.status_code, 302)
            with c.session_transaction() as sess:
                self.assertIn("_flashes", sess)
                self.assertIn("You have been logged out.", str(sess["_flashes"]))

    def test_login_with_invalid_credentials(self):
        create_user(
            username="testuser_invalid",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser_invalid@example.com",
        )
        response = self.login("testuser_invalid", "WrongPassword!")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

    def test_access_protected_route_without_login(self):
        create_user(is_admin=True, email="protectedroute@example.com")
        response = self.app.get("/user/dashboard", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        response = self.app.get(response.location)
        self.assertIn(b"Login", response.data)
        self.assertIn(b"Please log in to access this page.", response.data)
