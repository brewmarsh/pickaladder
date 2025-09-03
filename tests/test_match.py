from tests.helpers import BaseTestCase, create_user, create_match, TEST_PASSWORD
from pickaladder.models import User


class MatchTestCase(BaseTestCase):
    def test_create_match_page_load(self):
        create_user(
            username="testuser_match_load",
            password=TEST_PASSWORD,
            is_admin=True,
            email="testuser_match_load@example.com",
        )
        self.login("testuser_match_load", TEST_PASSWORD)
        response = self.app.get("/match/create")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Create Match", response.data)

    def test_create_match(self):
        create_user(
            username="winner_create",
            password=TEST_PASSWORD,
            is_admin=True,
            email="winner_create@example.com",
        )
        loser = create_user(
            username="loser_create",
            password=TEST_PASSWORD,
            email="loser_create@example.com",
        )
        self.login("winner_create", TEST_PASSWORD)
        response = self.app.post(
            "/match/create",
            data={
                "opponent": loser.id,
                "winner_score": 11,
                "loser_score": 5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match created successfully!", response.data)
        self.assertIn(b"winner_create", response.data)
        self.assertIn(b"loser_create", response.data)

    def test_view_match(self):
        winner = create_user(
            username="winner_view",
            password=TEST_PASSWORD,
            is_admin=True,
            email="winner_view@example.com",
        )
        loser = create_user(
            username="loser_view",
            password=TEST_PASSWORD,
            email="loser_view@example.com",
        )
        match = create_match(winner.id, loser.id)
        self.login("winner_view", TEST_PASSWORD)
        response = self.app.get(f"/match/{match.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"winner_view", response.data)
        self.assertIn(b"loser_view", response.data)
        self.assertIn(b"11", response.data)
        self.assertIn(b"5", response.data)

    def test_leaderboard_update(self):
        create_user(
            username="winner_leaderboard",
            password=TEST_PASSWORD,
            is_admin=True,
            email="winner_leaderboard@example.com",
        )
        loser = create_user(
            username="loser_leaderboard",
            password=TEST_PASSWORD,
            email="loser_leaderboard@example.com",
        )
        self.login("winner_leaderboard", TEST_PASSWORD)
        self.app.post(
            "/match/create",
            data={
                "opponent": loser.id,
                "winner_score": 11,
                "loser_score": 5,
            },
            follow_redirects=True,
        )

        response = self.app.get("/leaderboard")
        self.assertEqual(response.status_code, 200)
        # Winner should be higher on the leaderboard than the loser
        winner_pos = response.data.find(b"winner_leaderboard")
        loser_pos = response.data.find(b"loser_leaderboard")
        self.assertTrue(winner_pos < loser_pos)

        # Check ELO ratings
        winner_user = User.query.filter_by(username="winner_leaderboard").first()
        loser_user = User.query.filter_by(username="loser_leaderboard").first()
        self.assertGreater(winner_user.elo_rating, 1000)
        self.assertLess(loser_user.elo_rating, 1000)
