from tests.helpers import BaseTestCase, create_user


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
                "password": "Password123!",
                "confirm_password": "Password123!",
                "email": "new@example.com",
                "name": "New User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful. Please log in.", response.data)

    def test_login_logout(self):
        create_user(
            username="testuser",
            password="Password123!",
            is_admin=True,
            email="testuser@example.com",
        )
        # Test successful login
        response = self.login("testuser", "Password123!")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)
        self.assertIn(b"Logout", response.data)

        # Test successful logout
        response = self.app.get("/auth/logout", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have been logged out.", response.data)
        self.assertIn(b"Login", response.data)

    def test_login_with_invalid_credentials(self):
        create_user(
            username="testuser_invalid",
            password="Password123!",
            is_admin=True,
            email="testuser_invalid@example.com",
        )
        response = self.login("testuser_invalid", "WrongPassword!")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Invalid username or password", response.data)

    def test_access_protected_route_without_login(self):
        create_user(is_admin=True, email="protectedroute@example.com")
        response = self.app.get("/user/dashboard", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)
        self.assertIn(b"Please log in to access this page.", response.data)
