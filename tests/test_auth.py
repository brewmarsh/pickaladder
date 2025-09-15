from unittest.mock import patch
from tests.helpers import BaseTestCase, TEST_PASSWORD
from pickaladder.models import User
from pickaladder import db
from pickaladder.constants import USER_ID


class AuthTestCase(BaseTestCase):
    def test_login_page_load(self):
        self.create_user(is_admin=True, email="loginpage@example.com")
        response = self.app.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_install_with_invalid_dupr_rating(self):
        User.query.delete()
        db.session.commit()
        response = self.app.post(
            "/auth/install",
            data={
                "username": "admin",
                "password": TEST_PASSWORD,
                "email": "admin@example.com",
                "name": "Admin User",
                "dupr_rating": "invalid",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Invalid DUPR rating.", response.data)

    def test_successful_install_with_dupr(self):
        # Ensure no admin user exists
        User.query.delete()
        db.session.commit()
        response = self.app.post(
            "/auth/install",
            data={
                "username": "admin_dupr",
                "password": TEST_PASSWORD,
                "email": "admin_dupr@example.com",
                "name": "Admin DUPR",
                "dupr_rating": "4.5",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        admin_user = User.query.filter_by(username="admin_dupr").first()
        self.assertIsNotNone(admin_user)
        self.assertEqual(admin_user.dupr_rating, 4.5)

    def test_reset_password_with_token_page_load(self):
        user = self.create_user(is_admin=True, email="reset_page@example.com")
        token = user.get_reset_token()
        db.session.commit()  # Commit user to get token
        response = self.app.get(f"/auth/reset/{token}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Reset Your Password", response.data)

    def test_reset_password_with_invalid_token(self):
        self.create_user(is_admin=True, email="reset_invalid@example.com")
        response = self.app.get("/auth/reset/invalidtoken", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password reset link is invalid or has expired.", response.data)

    def test_reset_password_with_token_post(self):
        user = self.create_user(
            is_admin=True,
            username="reset_user",
            email="reset_post@example.com",
            password="old_password",  # nosec
        )
        token = user.get_reset_token()
        db.session.commit()
        response = self.app.post(
            f"/auth/reset/{token}",
            data={
                "password": "new_valid_password",
                "confirm_password": "new_valid_password",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Your password has been updated!", response.data)

        # Try to log in with the new password
        self.app.get("/auth/logout", follow_redirects=True)
        login_response = self.login(user.username, "new_valid_password")
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(b"Dashboard", login_response.data)

    def test_reset_password_with_token_password_mismatch(self):
        user = self.create_user(is_admin=True, email="reset_mismatch@example.com")
        token = user.get_reset_token()
        db.session.commit()
        response = self.app.post(
            f"/auth/reset/{token}",
            data={"password": "new_password", "confirm_password": "wrong_password"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Passwords do not match.", response.data)

    def test_reset_password_with_token_password_too_short(self):
        user = self.create_user(is_admin=True, email="reset_short@example.com")
        token = user.get_reset_token()
        db.session.commit()
        response = self.app.post(
            f"/auth/reset/{token}",
            data={"password": "short", "confirm_password": "short"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Password must be at least 8 characters long.", response.data)

    def test_change_password_page_load(self):
        user = self.create_user(
            username="changepasspage",
            password=TEST_PASSWORD,
            email="changepasspage@example.com",
        )
        self.login(user.username, TEST_PASSWORD)
        response = self.app.get("/auth/change_password")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Change Password", response.data)

    def test_change_password_not_logged_in(self):
        response = self.app.get("/auth/change_password", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_change_password_post(self):
        user = self.create_user(
            username="changepass",
            password=TEST_PASSWORD,
            email="changepass@example.com",
        )
        self.login(user.username, TEST_PASSWORD)
        response = self.app.post(
            "/auth/change_password",
            data={
                "password": "new_password_123",
                "confirm_password": "new_password_123",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Password changed successfully.", response.data)

        # Verify password was changed by logging in with new password
        self.app.get("/auth/logout", follow_redirects=True)
        login_response = self.login(user.username, "new_password_123")
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(b"Dashboard", login_response.data)

    def test_change_password_mismatch(self):
        user = self.create_user(
            username="changepassmismatch",
            password=TEST_PASSWORD,
            email="changepassmismatch@example.com",
        )
        self.login(user.username, TEST_PASSWORD)
        response = self.app.post(
            "/auth/change_password",
            data={"password": "new_password", "confirm_password": "wrong_password"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Passwords do not match.", response.data)

    def test_change_password_user_not_found_in_session(self):
        user = self.create_user(
            username="ghost", password=TEST_PASSWORD, email="ghost@example.com"
        )
        self.login(user.username, TEST_PASSWORD)

        # Now delete the user from the database
        db.session.delete(user)
        db.session.commit()

        with self.app.session_transaction() as sess:
            # Check that the user_id is in the session before the request
            self.assertIn(USER_ID, sess)

        response = self.app.get("/auth/change_password", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

        # Check that the session was cleared after the request
        with self.app.session_transaction() as sess:
            self.assertNotIn(USER_ID, sess)

    def test_forgot_password_page_load(self):
        self.create_user(is_admin=True, email="forgotpasswordpage@example.com")
        response = self.app.get("/auth/forgot_password")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Forgot Password", response.data)

    @patch("pickaladder.auth.routes.send_password_reset_email")
    def test_forgot_password_post(self, mock_send_email):
        user = self.create_user(is_admin=True, email="forgotpassword@example.com")
        response = self.app.post(
            "/auth/forgot_password",
            data={"email": user.email},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"If an account with that email exists, a password reset link has been sent.",
            response.data,
        )
        mock_send_email.assert_called_once_with(user)

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

    def test_register_with_existing_username(self):
        self.create_user(
            username="existinguser",
            password=TEST_PASSWORD,
            is_admin=True,
            email="existing_username@example.com",
        )
        response = self.app.post(
            "/auth/register",
            data={
                "username": "existinguser",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "email": "new_email@example.com",
                "name": "New User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Username already exists. Please choose a different one.", response.data
        )

    def test_register_with_existing_email(self):
        self.create_user(
            username="newuser",
            password=TEST_PASSWORD,
            is_admin=True,
            email="existing_email@example.com",
        )
        response = self.app.post(
            "/auth/register",
            data={
                "username": "anotheruser",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "email": "existing_email@example.com",
                "name": "Another User",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email address is already registered.", response.data)

    def test_login_logout(self):
        user = self.create_user(
            username="testuser",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser@example.com",
        )
        user.email_verified = True
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

    def test_login_with_unverified_email(self):
        # Enforce email verification
        self.create_setting("enforce_email_verification", "true")
        self.create_user(
            username="unverified_user_login",
            password=TEST_PASSWORD,
            email="unverified_login@example.com",
            email_verified=False,
            is_admin=True,
        )

        response = self.login("unverified_user_login", TEST_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Your email address is not verified. Please check your inbox for the verification link.",
            response.data,
        )

    def test_access_protected_route_without_login(self):
        self.create_user(is_admin=True, email="protectedroute@example.com")
        response = self.app.get("/user/dashboard", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)
        self.assertIn(b"Please log in to access this page.", response.data)

    @patch("pickaladder.auth.routes.mail.send")
    def test_email_verification(self, mock_mail_send):
        self.create_user(is_admin=True, email="verification@example.com")
        self.app.post(
            "/auth/register",
            data={
                "username": "unverified_user",
                "password": TEST_PASSWORD,
                "confirm_password": TEST_PASSWORD,
                "email": "unverified@example.com",
                "name": "Unverified User",
            },
            follow_redirects=True,
        )

        user = User.query.filter_by(username="unverified_user").first()
        self.assertFalse(user.email_verified)

        token = user.get_email_verification_token()

        response = self.app.get(f"/auth/verify_email/{token}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"Email verified successfully. You can now log in.", response.data
        )

        user = User.query.filter_by(username="unverified_user").first()
        self.assertTrue(user.email_verified)

    def test_email_verification_invalid_token(self):
        self.create_user(is_admin=True, email="invalidtoken@example.com")
        response = self.app.get(
            "/auth/verify_email/invalidtoken", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"The email verification link is invalid or has expired.", response.data
        )

    def test_install_page_load(self):
        # Ensure no admin user exists
        User.query.delete()
        db.session.commit()
        response = self.app.get("/auth/install")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create Admin Account", response.data)

    def test_successful_install(self):
        # Ensure no admin user exists
        User.query.delete()
        db.session.commit()
        response = self.app.post(
            "/auth/install",
            data={
                "username": "admin",
                "password": TEST_PASSWORD,
                "email": "admin@example.com",
                "name": "Admin User",
                "dupr_rating": "",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Dashboard", response.data)
        admin_user = User.query.filter_by(username="admin").first()
        self.assertIsNotNone(admin_user)
        self.assertTrue(admin_user.is_admin)

    def test_install_with_existing_admin(self):
        self.create_user(is_admin=True, email="existingadmin@example.com")
        response = self.app.get("/auth/install", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)
