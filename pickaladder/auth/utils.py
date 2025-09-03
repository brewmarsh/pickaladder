from PIL import Image, ImageDraw, ImageFont
import os
import uuid
from flask import url_for, current_app
from flask_mail import Message  # type: ignore
from pickaladder import mail
from werkzeug.security import generate_password_hash

from pickaladder import db
from pickaladder.models import User


def create_user(username, password, email, name, dupr_rating=None, is_admin=False):
    """Creates and prepares a new user object for database insertion."""
    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
    profile_picture_path, thumbnail_path = generate_profile_picture(name)

    new_user = User(
        username=username,
        password=hashed_password,
        email=email,
        name=name,
        dupr_rating=dupr_rating,
        is_admin=is_admin,
        profile_picture_path=profile_picture_path,
        profile_picture_thumbnail_path=thumbnail_path,
    )
    db.session.add(new_user)
    return new_user


def send_password_reset_email(user):
    """
    Sends a password reset email to the user.
    """
    token = user.get_reset_token()
    reset_url = url_for(
        "auth.reset_password_with_token", token=token, _external=True
    )
    msg = Message(
        "Password Reset Request",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[user.email],
    )
    msg.body = (
        f"To reset your password, visit the following link:\n{reset_url}\n\n"
        "If you did not make this request then simply ignore this email and no "
        "changes will be made."
    )
    mail.send(msg)


def generate_profile_picture(name):
    """
    Generates a profile picture with the user's initials and saves it to the filesystem.
    Returns the paths to the saved image and thumbnail.
    """
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    img = Image.open(os.path.join(static_dir, "user_icon.png")).convert("RGB")
    d = ImageDraw.Draw(img)
    first_name = name.split()[0]

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 40)
    except IOError:
        font = ImageFont.load_default()

    bbox = font.getbbox(first_name)
    text_width = bbox[2] - bbox[0]
    position = ((256 - text_width) / 2, 20)
    d.text(position, first_name, fill=(128, 128, 128), font=font)

    unique_id = uuid.uuid4().hex
    filename = f"{unique_id}_profile.png"
    filepath = os.path.join(upload_folder, filename)
    img.save(filepath, format="PNG")

    thumbnail_filename = f"{unique_id}_thumbnail.png"
    thumbnail_filepath = os.path.join(upload_folder, thumbnail_filename)
    img.thumbnail((64, 64))
    img.save(thumbnail_filepath, format="PNG")

    return filename, thumbnail_filename
