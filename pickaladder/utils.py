"""Utility functions for the application."""

import smtplib

from flask import current_app, render_template
from flask_mail import Message

from .extensions import mail

SMTP_AUTH_ERROR_CODE = 534


class EmailError(Exception):
    """Base class for email errors."""

    pass


# TODO: Add type hints for Agent clarity
def send_email(to, subject, template, **kwargs):
    """Send an email to a recipient.

    Raises:
        EmailError: If sending the email fails.
    """
    msg = Message(
        subject,
        recipients=[to],
        html=render_template(template, **kwargs),
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    try:
        mail.send(msg)
    except smtplib.SMTPAuthenticationError as e:
        if e.smtp_code == SMTP_AUTH_ERROR_CODE:
            error_message = (
                f"Authentication failed with code {SMTP_AUTH_ERROR_CODE}. This "
                "specifically means Google rejected the password because it expects "
                "an App Password. Even if your password is 16 characters, please "
                "ensure it is a freshly generated App Password, not your regular "
                "account password. See "
                "https://support.google.com/accounts/answer/185833"
            )
            raise EmailError(error_message) from e
        raise EmailError(f"SMTP Authentication failed: {e}") from e
    except Exception as e:
        raise EmailError(f"Failed to send email: {e}") from e
