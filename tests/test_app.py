import unittest
from app import app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
        self.app = app.test_client()

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
                "password": "Password123",
                "confirm_password": "Password123",
                "email": "test@example.com",
                "name": "Test User",
                "submit": "Register"
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
                "submit": "Register"
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Field must be equal to password.", response.data)

    def test_register_validation_password_too_weak(self):
        response = self.app.post(
            "/auth/register",
            data={
                "username": "testuser",
                "password": "weak",
                "confirm_password": "weak",
                "email": "test@example.com",
                "name": "Test User",
                "submit": "Register"
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password must be at least 8 characters long", response.data)

    def test_create_match_requires_login(self):
        response = self.app.get("/match/create", follow_redirects=True)
        # Should redirect to login page, which then redirects to install
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/install", response.location)

    def test_forgot_password_post_redirects_and_flashes(self):
        response = self.app.post(
            "/auth/forgot_password",
            data={"email": "test@example.com"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 302)  # Should redirect to install
        self.assertIn("/auth/install", response.location)

    def test_reset_with_invalid_token(self):
        response = self.app.get("/auth/reset/invalidtoken", follow_redirects=True)
        self.assertEqual(response.status_code, 302)  # Should redirect to install
        self.assertIn("/auth/install", response.location)


if __name__ == "__main__":
    unittest.main()
