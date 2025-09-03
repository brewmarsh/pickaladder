import unittest
from app import app
from pickaladder import db
from pickaladder.models import User, Match, Friend
from werkzeug.security import generate_password_hash


TEST_PASSWORD = "Password123!"  # nosec


def create_user(username="testuser", password=TEST_PASSWORD, email="test@example.com", name="Test User", is_admin=False):
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


def create_match(winner_id, loser_id, winner_score=11, loser_score=5):
    """Creates a match in the database and returns the match object."""
    match = Match(
        winner_id=winner_id,
        loser_id=loser_id,
        winner_score=winner_score,
        loser_score=loser_score,
    )
    db.session.add(match)
    db.session.commit()
    return match


def send_friend_request(from_user_id, to_user_id):
    """Creates a friend request in the database."""
    friend_request = Friend(
        user_id=from_user_id,
        friend_id=to_user_id,
        is_accepted=False,
    )
    db.session.add(friend_request)
    db.session.commit()


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://user:password@db/test_db"
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, username, password):
        return self.app.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )
