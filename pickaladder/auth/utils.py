from PIL import Image, ImageDraw, ImageFont
import io
import os
from flask import url_for, current_app
from flask_mail import Message
from pickaladder import mail


def send_password_reset_email(user):
    """
    Sends a password reset email to the user.
    """
    token = user.get_reset_token()
    reset_url = url_for("auth.reset_password_with_token", token=token, _external=True)
    msg = Message(
        "Password Reset Request",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[user.email],
    )
    msg.body = f"""To reset your password, visit the following link:
{reset_url}

If you did not make this request then simply ignore this email and no changes will be made.
"""
    mail.send(msg)


def generate_profile_picture(name):
    """
    Generates a profile picture with the user's initials.
    """
    # Get the absolute path to the static directory
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    img = Image.open(os.path.join(static_dir, "user_icon.png")).convert("RGB")
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
