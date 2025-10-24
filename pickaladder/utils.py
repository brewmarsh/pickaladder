"""Utility functions for the application."""
from flask import current_app, render_template
from flask_mail import Message

from .extensions import mail


def send_email(to, subject, template, **kwargs):
    """Send an email to a recipient."""
    msg = Message(
        subject,
        recipients=[to],
        html=render_template(template, **kwargs),
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    mail.send(msg)
