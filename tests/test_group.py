from tests.helpers import BaseTestCase, TEST_PASSWORD
from pickaladder.models import Friend, Group, GroupMember
from pickaladder import db


class GroupTestCase(BaseTestCase):
    def test_create_group(self):
        user = self.create_user(
            username="group_creator",
            password=TEST_PASSWORD,
            is_admin=True,
            email="group_creator@example.com",
        )
        self.login("group_creator", TEST_PASSWORD)
        response = self.app.post(
            "/group/create",
            data={"name": "Test Group"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group created successfully.", response.data)
        group = Group.query.filter_by(name="Test Group").first()
        self.assertIsNotNone(group)
        self.assertEqual(group.owner_id, user.id)
        # Check if the creator is a member
        member = GroupMember.query.filter_by(group_id=group.id, user_id=user.id).first()
        self.assertIsNotNone(member)

    def test_invite_to_group(self):
        owner = self.create_user(
            username="group_owner_invite",
            password=TEST_PASSWORD,
            is_admin=True,
            email="group_owner_invite@example.com",
        )
        friend_user = self.create_user(
            username="friend_to_invite",
            password=TEST_PASSWORD,
            email="friend_to_invite@example.com",
        )
        # Establish friendship
        friendship1 = Friend(
            user_id=owner.id, friend_id=friend_user.id, status="accepted"
        )
        friendship2 = Friend(
            user_id=friend_user.id, friend_id=owner.id, status="accepted"
        )
        db.session.add_all([friendship1, friendship2])
        db.session.commit()

        self.login("group_owner_invite", TEST_PASSWORD)
        group = self.create_group(name="Invite Test Group", owner_id=owner.id)
        self.add_user_to_group(group.id, owner.id)

        response = self.app.post(
            f"/group/{group.id}",
            data={"friend": str(friend_user.id)},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Friend invited successfully.", response.data)
        member = GroupMember.query.filter_by(
            group_id=group.id, user_id=friend_user.id
        ).first()
        self.assertIsNotNone(member)

    def test_group_leaderboard(self):
        owner = self.create_user(
            username="leaderboard_owner",
            name="Leaderboard Owner",
            password=TEST_PASSWORD,
            is_admin=True,
            email="leaderboard_owner@example.com",
        )
        member1 = self.create_user(
            username="leaderboard_member1",
            name="Leaderboard Member 1",
            password=TEST_PASSWORD,
            email="leaderboard_member1@example.com",
        )
        member2 = self.create_user(
            username="leaderboard_member2",
            name="Leaderboard Member 2",
            password=TEST_PASSWORD,
            email="leaderboard_member2@example.com",
        )
        non_member = self.create_user(
            username="non_member",
            name="Non Member",
            password=TEST_PASSWORD,
            email="non_member@example.com",
        )

        group = self.create_group(name="Leaderboard Group", owner_id=owner.id)
        self.add_user_to_group(group.id, owner.id)
        self.add_user_to_group(group.id, member1.id)
        self.add_user_to_group(group.id, member2.id)

        # Match between group members (should be on leaderboard)
        self.create_match(member1.id, member2.id, 11, 5)
        # Match with a non-group member (should not be on leaderboard)
        self.create_match(owner.id, non_member.id, 11, 2)

        self.login("leaderboard_owner", TEST_PASSWORD)
        response = self.app.get(f"/group/{group.id}")
        self.assertEqual(response.status_code, 200)

        # Member 1 should be on the leaderboard
        self.assertIn(b"Leaderboard Member 1", response.data)
        # Member 2 should be on the leaderboard
        self.assertIn(b"Leaderboard Member 2", response.data)
        # The owner should not be on the leaderboard yet (0 games played)
        self.assertNotIn(b"Leaderboard Owner", response.data)
        # The non-member should not be on the leaderboard
        self.assertNotIn(b"Non Member", response.data)

        # Check order
        member1_pos = response.data.find(b"Leaderboard Member 1")
        member2_pos = response.data.find(b"Leaderboard Member 2")
        self.assertTrue(member1_pos < member2_pos)

    def test_delete_group_by_owner(self):
        owner = self.create_user(
            username="group_owner_delete",
            password=TEST_PASSWORD,
            is_admin=True,
            email="group_owner_delete@example.com",
        )
        self.login("group_owner_delete", TEST_PASSWORD)
        group = self.create_group(name="Group to Delete", owner_id=owner.id)
        group_id = group.id
        self.add_user_to_group(group.id, owner.id)

        response = self.app.post(f"/group/{group_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Group deleted successfully.", response.data)
        deleted_group = Group.query.get(group_id)
        self.assertIsNone(deleted_group)

    def test_delete_group_by_non_owner(self):
        owner = self.create_user(
            username="group_owner_nodelete",
            password=TEST_PASSWORD,
            is_admin=True,
            email="group_owner_nodelete@example.com",
        )
        non_owner = self.create_user(
            username="non_owner_delete_attempt",
            password=TEST_PASSWORD,
            email="non_owner_delete_attempt@example.com",
        )
        group = self.create_group(name="No Delete Group", owner_id=owner.id)
        group_id = group.id
        self.add_user_to_group(group.id, owner.id)
        self.add_user_to_group(group.id, non_owner.id)

        self.login("non_owner_delete_attempt", TEST_PASSWORD)
        response = self.app.post(f"/group/{group_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b"You do not have permission to delete this group.", response.data
        )
        not_deleted_group = Group.query.get(group_id)
        self.assertIsNotNone(not_deleted_group)
