from flask import render_template
from flask_mail import Message
from .extensions import mail

def send_email(to, subject, template, **kwargs):
    """
    Sends an email to a recipient.
    """
    msg = Message(
        subject,
        recipients=[to],
        html=render_template(template, **kwargs),
        sender="noreply@pickaladder.com"
    )
    mail.send(msg)