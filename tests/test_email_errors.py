
import unittest
from unittest.mock import patch, MagicMock
import smtplib
from pickaladder.utils import send_email, EmailError
from pickaladder import create_app

class TestEmailErrors(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "MAIL_SUPPRESS_SEND": False})
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch("pickaladder.utils.mail.send")
    def test_send_email_smtp_534(self, mock_send):
        # specific 534 error
        error_msg = b'5.7.9 Please log in with your web browser and then try again...'
        mock_send.side_effect = smtplib.SMTPAuthenticationError(534, error_msg)

        # We expect EmailError to be raised with a friendly message
        with self.assertRaises(EmailError) as cm:
            send_email("test@example.com", "Subject", "email/group_invite.html",
                       name="Test", group_name="TestGroup", invite_url="http://example.com")

        self.assertIn("Google requires you to sign in via a web browser", str(cm.exception))

    @patch("pickaladder.utils.mail.send")
    def test_send_email_generic_error(self, mock_send):
        # Generic error
        mock_send.side_effect = Exception("Some other error")

        with self.assertRaises(EmailError) as cm:
            send_email("test@example.com", "Subject", "email/group_invite.html",
                       name="Test", group_name="TestGroup", invite_url="http://example.com")

        self.assertIn("Failed to send email: Some other error", str(cm.exception))
