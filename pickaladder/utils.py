"""Utility functions for the application."""

from __future__ import annotations

from typing import Any

from pickaladder.services.mail_service import MailService


def send_email(to: str | list[str], subject: str, template: str, **kwargs: Any) -> None:
    """Send an email to a recipient asynchronously.

    This function is maintained for backward compatibility.
    """
    MailService.send_email(to, subject, template, **kwargs)


def mask_email(email: str) -> str:
    """Mask an email address for display.

    Example: march@gmail.com -> m...h@gmail.com
    """
    if not email or "@" not in email:
        return email
    local, domain = email.split("@")
    if len(local) <= 1:
        return f"{local}...@{domain}"
    return f"{local[0]}...{local[-1]}@{domain}"
