"""Utility functions for the application."""

import smtplib

from flask import current_app, render_template
from flask_mail import Message

from .extensions import mail


class EmailError(Exception):
    """Base class for email errors."""

    pass


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
        if e.smtp_code == 534:
            raise EmailError(
                "Authentication failed. Google requires you to use an App Password. "
                "Please verify your MAIL_USERNAME and MAIL_PASSWORD settings. "
                "See https://support.google.com/accounts/answer/185833 for instructions on how to generate an App Password."
            ) from e
        raise EmailError(f"SMTP Authentication failed: {e}") from e
    except Exception as e:
        raise EmailError(f"Failed to send email: {e}") from e
