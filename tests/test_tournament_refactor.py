import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.tournament.services.tournament_service import TournamentService


class TournamentRefactorTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False}
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.db = MagicMock()

    def tearDown(self):
        self.app_context.pop()

    @patch("pickaladder.tournament.services.tournament_service.firestore")
    def test_build_create_payload_includes_format(self, mock_firestore):
        user_ref = MagicMock()
        user_ref.id = "user123"
        data = {
            "name": "Test Tourney",
            "date": "2024-01-01",
            "venue_name": "Court 1",
            "matchType": "doubles",
            "format": "POOL_PLAY",
            "pool_count": 4,
            "promoted_per_pool": 2,
        }

        payload = TournamentService._build_create_payload(data, "user123", user_ref)

        self.assertEqual(payload["format"], "POOL_PLAY")
        self.assertEqual(payload["pool_count"], 4)
        self.assertEqual(payload["promoted_per_pool"], 2)
        self.assertEqual(payload["matchType"], "doubles")
        self.assertEqual(payload["mode"], "DOUBLES")


if __name__ == "__main__":
    unittest.main()
