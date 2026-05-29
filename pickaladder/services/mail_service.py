"""Service for sending emails asynchronously."""

from __future__ import annotations

import smtplib
from typing import Any

from flask import current_app, render_template
from flask_mail import Message

from pickaladder.core.constants import SMTP_AUTH_ERROR_CODE
from pickaladder.extensions import executor, mail


class EmailError(Exception):
    """Base class for email errors."""


class MailService:
    """Service for handling email operations."""

    @staticmethod
    def send_email_now(
        to: str | list[str],
        subject: str,
        template: str,
        **kwargs: Any,
    ) -> None:
        """Send an email synchronously.

        This method is intended to be called within a background thread.
        It expects to be running within a Flask application context.

        Raises:
            EmailError: If sending the email fails.
        """
        # Ensure 'to' is a list
        recipients = [to] if isinstance(to, str) else to

        msg = Message(
            subject,
            recipients=recipients,
            html=render_template(template, **kwargs),
            sender=current_app.config["MAIL_DEFAULT_SENDER"],
        )
        try:
            mail.send(msg)
            current_app.logger.info(
                f"Email sent successfully: {subject} to {recipients}",
            )
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
                current_app.logger.exception(error_message)
                raise EmailError(error_message) from e
            error_msg = f"SMTP Authentication failed: {e}"
            current_app.logger.exception(error_msg)
            raise EmailError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to send email: {e}"
            current_app.logger.exception(error_msg)
            raise EmailError(error_msg) from e

    @staticmethod
    def send_email(
        to: str | list[str],
        subject: str,
        template: str,
        **kwargs: Any,
    ) -> None:
        """Send an email asynchronously in a background thread.

        This is the preferred method for sending emails from route handlers
        to avoid blocking the HTTP response.
        """
        executor.run_async(
            MailService.send_email_now,
            to=to,
            subject=subject,
            template=template,
            **kwargs,
        )
