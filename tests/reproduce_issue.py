
import unittest
from unittest.mock import MagicMock, patch
from pickaladder.match.services import MatchQueryService

class TestMatchQueryService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()

    @patch("pickaladder.match.services.MatchQueryService._process_match_document")
    def test_get_latest_matches(self, mock_process):
        mock_doc = MagicMock()
        mock_doc.id = "match1"

        self.db.collection.return_value.order_by.return_value.limit.return_value.stream.return_value = [mock_doc]

        mock_process.return_value = {"id": "match1", "processed": True}

        results = MatchQueryService.get_latest_matches(self.db, limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "match1")
        self.assertTrue(results[0]["processed"])

        self.db.collection.assert_called_with("matches")
        mock_process.assert_called_once_with(mock_doc, self.db)

if __name__ == "__main__":
    unittest.main()
