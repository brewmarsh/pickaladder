from . import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func

from flask import current_app
from itsdangerous import URLSafeTimedSerializer as Serializer


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    username = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, nullable=False)
    email = db.Column(db.String, unique=True, nullable=True)
    name = db.Column(db.String)
    dupr_rating = db.Column(db.Numeric(3, 2))
    is_admin = db.Column(db.Boolean, default=False)
    # profile_picture = db.Column(db.LargeBinary)  # Deprecated
    # profile_picture_thumbnail = db.Column(db.LargeBinary)  # Deprecated
    profile_picture_path = db.Column(db.String(255))
    profile_picture_thumbnail_path = db.Column(db.String(255))
    dark_mode = db.Column(db.Boolean, default=False)
    email_verified = db.Column(db.Boolean, default=False)

    # These columns are no longer needed as the token contains the user id and expiration
    # reset_token = db.Column(db.String)
    # reset_token_expiration = db.Column(db.DateTime(timezone=True))

    # Relationships
    matches_as_player1 = db.relationship(
        "Match", foreign_keys="Match.player1_id", backref="player1", lazy=True
    )
    matches_as_player2 = db.relationship(
        "Match", foreign_keys="Match.player2_id", backref="player2", lazy=True
    )

    # Friendships initiated by this user
    friend_requests_sent = db.relationship(
        "Friend",
        foreign_keys="Friend.user_id",
        backref="requester",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    # Friendships received by this user
    friend_requests_received = db.relationship(
        "Friend",
        foreign_keys="Friend.friend_id",
        backref="requested",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config["SECRET_KEY"])
        return s.dumps({"user_id": str(self.id)})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config["SECRET_KEY"])
        try:
            user_id = s.loads(token, max_age=expires_sec)["user_id"]
        except Exception:
            return None
        return User.query.get(user_id)

    def __repr__(self):
        return f"<User {self.username}>"


class Friend(db.Model):
    __tablename__ = "friends"
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    friend_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status = db.Column(db.String, default="pending", nullable=False)

    def __repr__(self):
        return f"<Friendship from {self.user_id} to {self.friend_id}>"


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.uuid_generate_v4()
    )
    player1_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False
    )
    player2_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False
    )
    player1_score = db.Column(db.Integer)
    player2_score = db.Column(db.Integer)
    match_date = db.Column(db.Date)

    def __repr__(self):
        return f"<Match {self.id}>"
