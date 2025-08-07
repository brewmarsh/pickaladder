from PIL import Image, ImageDraw, ImageFont
import io
import os
import secrets
from datetime import datetime, timedelta
from flask import url_for, current_app
from flask_mail import Message
from werkzeug.security import generate_password_hash
from pickaladder.db import get_db_connection
from pickaladder import mail
from pickaladder.constants import (
    USERS_TABLE,
    USER_ID,
    USER_EMAIL,
    USER_RESET_TOKEN,
    USER_RESET_TOKEN_EXPIRATION,
)
import psycopg2


def send_password_reset_email(email):
    """
    Generates a password reset token, stores it in the database, and sends the reset email.
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(f"SELECT * FROM {USERS_TABLE} WHERE {USER_EMAIL} = %s", (email,))
    user = cur.fetchone()

    if user:
        token = secrets.token_urlsafe(32)
        token_hash = generate_password_hash(token)
        expiration = datetime.utcnow() + timedelta(hours=1)

        cur.execute(
            f"UPDATE {USERS_TABLE} SET {USER_RESET_TOKEN} = %s, {USER_RESET_TOKEN_EXPIRATION} = %s WHERE {USER_ID} = %s",
            (token_hash, expiration, user[USER_ID]),
        )
        conn.commit()

        reset_url = url_for("auth.reset_password_with_token", token=token, _external=True)
        msg = Message(
            "Password Reset Request",
            sender=current_app.config["MAIL_USERNAME"],
            recipients=[email],
        )
        msg.body = f"To reset your password, visit the following link: {reset_url}\n\nIf you did not make this request then simply ignore this email and no changes will be made."
        mail.send(msg)


def generate_profile_picture(name):
    """
    Generates a profile picture with the user's initials.
    """
    # Get the absolute path to the static directory
    static_dir = os.path.join(os.path.dirname(__file__), '..', 'static')
    img = Image.open(os.path.join(static_dir, 'user_icon.png')).convert("RGB")
    d = ImageDraw.Draw(img)
    first_name = name.split()[0]

    # Use a truetype font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
    except IOError:
        font = ImageFont.load_default()

    # Center the text horizontally, and position it towards the top vertically
    bbox = font.getbbox(first_name)
    text_width = bbox[2] - bbox[0]
    position = ((256 - text_width) / 2, 20)

    d.text(position, first_name, fill=(128, 128, 128), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    profile_picture_data = buf.getvalue()

    img.thumbnail((64, 64))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    thumbnail_data = buf.getvalue()

    return profile_picture_data, thumbnail_data
