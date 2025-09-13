from tests.helpers import BaseTestCase, TEST_PASSWORD
from pickaladder.models import Friend


class UserTestCase(BaseTestCase):
    def test_view_own_profile(self):
        user = self.create_user(
            username="testuser_profile",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser_profile@example.com",
        )
        self.login("testuser_profile", TEST_PASSWORD)
        response = self.app.get(f"/user/{user.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"testuser_profile", response.data)

    def test_view_other_user_profile(self):
        self.create_user(
            username="user1_view",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_view@example.com",
        )
        user2 = self.create_user(
            username="user2_view",
            password=TEST_PASSWORD,
            email="user2_view@example.com",
        )
        self.login("user1_view", TEST_PASSWORD)
        response = self.app.get(f"/user/{user2.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"user2_view", response.data)

    def test_send_friend_request(self):
        user1 = self.create_user(
            username="user1_friend_send",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_send@example.com",
        )
        user2 = self.create_user(
            username="user2_friend_send",
            password=TEST_PASSWORD,
            email="user2_friend_send@example.com",
        )
        self.login("user1_friend_send", TEST_PASSWORD)
        response = self.app.post(
            f"/user/send_friend_request/{user2.id}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request sent.", response.data)

        # Verify the friend request exists in the database
        friend_request = Friend.query.filter_by(
            user_id=user1.id, friend_id=user2.id
        ).first()
        self.assertIsNotNone(friend_request)
        self.assertEqual(friend_request.status, "pending")

    def test_accept_friend_request(self):
        user1 = self.create_user(
            username="user1_friend_accept",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_accept@example.com",
        )
        user2 = self.create_user(
            username="user2_friend_accept",
            password=TEST_PASSWORD,
            email="user2_friend_accept@example.com",
        )
        self.send_friend_request(user1.id, user2.id)
        self.login("user2_friend_accept", TEST_PASSWORD)
        response = self.app.post(
            f"/user/accept_friend_request/{user1.id}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request accepted.", response.data)

        # Verify the friendship is established
        friendship = db.session.get(Friend, (user1.id, user2.id))
        self.assertEqual(friendship.status, "accepted")
        friendship2 = db.session.get(Friend, (user2.id, user1.id))
        self.assertEqual(friendship2.status, "accepted")

    def test_decline_friend_request(self):
        user1 = self.create_user(
            username="user1_friend_decline",
            password=TEST_PASSWORD,
            is_admin=True,
            email="user1_friend_decline@example.com",
        )
        user2 = self.create_user(
            username="user2_friend_decline",
            password=TEST_PASSWORD,
            email="user2_friend_decline@example.com",
        )
        self.send_friend_request(user1.id, user2.id)
        self.login("user2_friend_decline", TEST_PASSWORD)
        response = self.app.post(
            f"/user/decline_friend_request/{user1.id}", follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend request declined.", response.data)

        # Verify the friend request is deleted
        friend_request = db.session.get(Friend, (user1.id, user2.id))
        self.assertIsNone(friend_request)

    def test_dashboard_api_group_rankings(self):
        # Create users
        user = self.create_user(
            username="dashboard_user",
            password=TEST_PASSWORD,
            is_admin=True,
            email="dashboard_user@example.com",
        )
        member2 = self.create_user(
            username="dashboard_member2",
            password=TEST_PASSWORD,
            email="dashboard_member2@example.com",
        )

        # Create groups
        group1 = self.create_group(name="Dashboard Group 1", owner_id=user.id)
        group2 = self.create_group(name="Dashboard Group 2", owner_id=user.id)
        self.add_user_to_group(group1.id, user.id)
        self.add_user_to_group(group1.id, member2.id)
        self.add_user_to_group(group2.id, user.id)

        # Create a match in group 1
        self.create_match(user.id, member2.id, 5, 11)

        # Log in and get dashboard data
        self.login("dashboard_user", TEST_PASSWORD)
        response = self.app.get("/user/api/dashboard")
        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("group_rankings", data)
        self.assertEqual(len(data["group_rankings"]), 2)

        # Check rankings
        g1_found = False
        g2_found = False
        for ranking in data["group_rankings"]:
            if ranking["group_name"] == "Dashboard Group 1":
                g1_found = True
                # user lost, so they should be rank 2
                self.assertEqual(ranking["rank"], 2)
            elif ranking["group_name"] == "Dashboard Group 2":
                g2_found = True
                # No matches in this group, so rank is N/A
                self.assertEqual(ranking["rank"], "N/A")

        self.assertTrue(g1_found)
        self.assertTrue(g2_found)
