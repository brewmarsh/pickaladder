import unittest
from app import app
from pickaladder import db
from pickaladder.models import User, Match, Friend
from werkzeug.security import generate_password_hash


TEST_PASSWORD = "Password123!"  # nosec


def create_user(
    username="testuser",
    password=TEST_PASSWORD,
    email="test@example.com",
    name="Test User",
    is_admin=False,
):
    """Creates a user in the database and returns the user object."""
    hashed_password = generate_password_hash(password)
    user = User(
        username=username,
        password=hashed_password,
        email=email,
        name=name,
        is_admin=is_admin,
    )
    db.session.add(user)
    db.session.commit()
    return user


from datetime import date


def create_match(player1_id, player2_id, player1_score=11, player2_score=5, match_date=None):
    """Creates a match in the database and returns the match object."""
    if match_date is None:
        match_date = date.today()
    match = Match(
        player1_id=player1_id,
        player2_id=player2_id,
        player1_score=player1_score,
        player2_score=player2_score,
        match_date=match_date,
    )
    db.session.add(match)
    db.session.commit()
    return match


def send_friend_request(from_user_id, to_user_id):
    """Creates a friend request in the database."""
    friend_request = Friend(
        user_id=from_user_id, friend_id=to_user_id, status="pending"
    )
    db.session.add(friend_request)
    db.session.commit()


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["MAIL_SUPPRESS_SEND"] = True
        self.app = app.test_client()
        self.ctx = app.app_context()  # Create and store context
        self.ctx.push()               # Push the context
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()                # Pop the context

    def login(self, username, password):
        return self.app.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )
