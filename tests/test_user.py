from tests.helpers import BaseTestCase, create_user, send_friend_request, TEST_PASSWORD
from pickaladder.models import Friend, User


class UserTestCase(BaseTestCase):
    def test_view_own_profile(self):
        user = create_user(
            username="testuser_profile",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser_profile@example.com",
        )
        self.login("testuser_profile", TEST_PASSWORD)
        response = self.app.get(f"/user/profile/{user.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"testuser_profile", response.data)

    def test_view_other_user_profile(self):
        create_user(
            username="user1_view",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_view@example.com",
        )
        user2 = create_user(
            username="user2_view",
            password=TEST_PASSWORD,
            email="user2_view@example.com",
        )
        self.login("user1_view", TEST_PASSWORD)
        response = self.app.get(f"/user/profile/{user2.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"user2_view", response.data)

    def test_send_friend_request(self):
        user1 = create_user(
            username="user1_friend_send",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_send@example.com",
        )
        user2 = create_user(
            username="user2_friend_send",
            password=TEST_PASSWORD,
            email="user2_friend_send@example.com",
        )
        self.login("user1_friend_send", TEST_PASSWORD)
        response = self.app.post(f"/user/friend/add/{user2.id}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request sent.", response.data)

        # Verify the friend request exists in the database
        friend_request = Friend.query.filter_by(
            user_id=user1.id, friend_id=user2.id
        ).first()
        self.assertIsNotNone(friend_request)
        self.assertFalse(friend_request.is_accepted)

    def test_accept_friend_request(self):
        user1 = create_user(
            username="user1_friend_accept",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_accept@example.com",
        )
        user2 = create_user(
            username="user2_friend_accept",
            password=TEST_PASSWORD,
            email="user2_friend_accept@example.com",
        )
        send_friend_request(user1.id, user2.id)
        self.login("user2_friend_accept", TEST_PASSWORD)
        friend_request = Friend.query.filter_by(
            user_id=user1.id, friend_id=user2.id
        ).first()
        response = self.app.post(
            f"/user/friend/accept/{friend_request.id}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request accepted.", response.data)

        # Verify the friendship is established
        friendship = Friend.query.get(friend_request.id)
        self.assertTrue(friendship.is_accepted)

    def test_decline_friend_request(self):
        user1 = create_user(
            username="user1_friend_decline",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_decline@example.com",
        )
        user2 = create_user(
            username="user2_friend_decline",
            password=TEST_PASSWORD,
            email="user2_friend_decline@example.com",
        )
        send_friend_request(user1.id, user2.id)
        self.login("user2_friend_decline", TEST_PASSWORD)
        friend_request = Friend.query.filter_by(
            user_id=user1.id, friend_id=user2.id
        ).first()
        response = self.app.post(
            f"/user/friend/decline/{friend_request.id}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request declined.", response.data)

        # Verify the friend request is deleted
        friend_request = Friend.query.get(friend_request.id)
        self.assertIsNone(friend_request)
