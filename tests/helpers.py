import unittest
import datetime
from app import app
from pickaladder import db
from pickaladder.models import User, Match, Friend, Setting
from werkzeug.security import generate_password_hash
from pickaladder.constants import USER_ID, USER_IS_ADMIN


TEST_PASSWORD = "Password123!"  # nosec


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_user(
        self,
        username="testuser",
        password=TEST_PASSWORD,
        email="test@example.com",
        name="Test User",
        is_admin=False,
        email_verified=True,
    ):
        """Creates a user in the database and returns the user object."""
        hashed_password = generate_password_hash(password)
        user = User(
            username=username,
            password=hashed_password,
            email=email,
            name=name,
            is_admin=is_admin,
            email_verified=email_verified,
        )
        db.session.add(user)
        db.session.commit()
        return user

    def create_match(
        self, player1_id, player2_id, player1_score=11, player2_score=5, match_date=None
    ):
        """Creates a match in the database and returns the match object."""
        if match_date is None:
            match_date = datetime.date.today()
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

    def send_friend_request(self, from_user_id, to_user_id):
        """Creates a friend request in the database."""
        friend_request = Friend(
            user_id=from_user_id,
            friend_id=to_user_id,
            status="pending",
        )
        db.session.add(friend_request)
        db.session.commit()

    def login(self, username, password):
        user = User.query.filter_by(username=username).first()
        if user:
            with self.app as c:
                with c.session_transaction() as sess:
                    sess[USER_ID] = str(user.id)
                    sess[USER_IS_ADMIN] = user.is_admin
        return self.app.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )

    def create_group(self, name, owner_id, description="", is_public=False):
        """Creates a group in the database and returns the group object."""
        from pickaladder.models import Group

        group = Group(
            name=name,
            owner_id=owner_id,
            description=description,
            is_public=is_public,
        )
        db.session.add(group)
        db.session.commit()
        return group

    def add_user_to_group(self, group_id, user_id):
        """Adds a user to a group in the database."""
        from pickaladder.models import GroupMember

        member = GroupMember(group_id=group_id, user_id=user_id)
        db.session.add(member)
        db.session.commit()

    def create_setting(self, key, value):
        """Creates a setting in the database and returns the setting object."""
        setting = Setting(key=key, value=value)
        db.session.add(setting)
        db.session.commit()
        return setting
