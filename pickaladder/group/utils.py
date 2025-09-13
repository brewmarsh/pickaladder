import os
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from flask import current_app
from sqlalchemy import or_, case, func
from pickaladder import db
from pickaladder.models import User, Match, Group


def save_group_picture(form_picture):
    unique_id = uuid.uuid4().hex
    filename = secure_filename(f"{unique_id}_group_profile.png")
    thumbnail_filename = secure_filename(f"{unique_id}_group_thumbnail.png")

    upload_folder = os.path.join(current_app.static_folder, "uploads")
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    img = Image.open(form_picture)
    img.thumbnail((512, 512))
    filepath = os.path.join(upload_folder, filename)
    img.save(filepath, format="PNG")

    img.thumbnail((64, 64))
    thumbnail_filepath = os.path.join(upload_folder, thumbnail_filename)
    img.save(thumbnail_filepath, format="PNG")

    return filename, thumbnail_filename


def get_group_leaderboard(group_id):
    """
    Calculates the leaderboard for a specific group.
    """
    group = db.session.get(Group, group_id)
    if not group:
        return []

    member_ids = [m.user_id for m in group.members]

    player_score = case(
        (Match.player1_id == User.id, Match.player1_score),
        else_=Match.player2_score,
    )
    leaderboard = (
        db.session.query(
            User.id,
            User.name,
            func.avg(player_score).label("avg_score"),
            func.count(Match.id).label("games_played"),
        )
        .join(Match, or_(User.id == Match.player1_id, User.id == Match.player2_id))
        .filter(User.id.in_(member_ids))
        .filter(Match.player1_id.in_(member_ids))
        .filter(Match.player2_id.in_(member_ids))
        .group_by(User.id, User.name)
        .order_by(func.avg(player_score).desc())
        .all()
    )
    return leaderboard
