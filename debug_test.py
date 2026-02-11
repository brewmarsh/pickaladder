import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class TestDebug(unittest.TestCase):
    def test_debug_summary(self):
        app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SECRET_KEY": "test"}
        )
        with app.test_client() as client:
            with patch(
                "pickaladder.match.routes.MatchService.get_match_by_id"
            ) as mock_get:
                mock_get.return_value = {
                    "id": "m123",
                    "matchType": "singles",
                    "player1Score": 11,
                    "player2Score": 5,
                    "player1Ref": MagicMock(id="u1"),
                    "player2Ref": MagicMock(id="u2"),
                    "matchDate": MagicMock(),
                }
                with patch("pickaladder.match.routes.firestore.client") as mock_db:
                    db = MagicMock()
                    mock_db.return_value = db
                    # Mock player fetch
                    p_doc = MagicMock()
                    p_doc.exists = True
                    p_doc.to_dict.return_value = {"name": "User 1"}
                    p_doc.id = "u1"
                    db.collection.return_value.document.return_value.get.return_value = p_doc

                    with app.test_request_context():
                        from flask import g, session

                        session["user_id"] = "u1"
                        g.user = {"uid": "u1", "name": "User 1"}

                        response = client.get("/match/summary/m123")
                        print(f"Status: {response.status_code}")
                        data = response.get_data(as_text=True)
                        print(f"Found 'Match Summary': {'Match Summary' in data}")
                        if "Match Summary" not in data:
                            print(data[:500])


if __name__ == "__main__":
    unittest.main()
