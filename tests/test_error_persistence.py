import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.services.error_service import ErrorService


class ErrorPersistenceTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False}
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.req_context = self.app.test_request_context()
        self.req_context.push()
        self.db = MagicMock()

    def tearDown(self):
        self.req_context.pop()
        self.app_context.pop()

    @patch("pickaladder.services.error_service.firestore")
    @patch("pickaladder.services.error_service.request")
    def test_log_error_persists_to_firestore(self, mock_request, mock_firestore):
        mock_firestore.client.return_value = self.db
        mock_request.url = "http://test.com"
        mock_request.method = "GET"
        mock_request.headers = {"User-Agent": "test-agent"}

        # Setup mock for db.collection().add()
        mock_coll = MagicMock()
        self.db.collection.return_value = mock_coll
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "error123"
        mock_coll.add.return_value = (None, mock_doc_ref)

        try:
            raise ValueError("Test error")
        except ValueError as e:
            error_id = ErrorService.log_error(e)

        self.assertEqual(error_id, "error123")
        self.db.collection.assert_called_with("system_errors")

        # Verify data sent to Firestore
        args, kwargs = mock_coll.add.call_args
        data = args[0]
        self.assertEqual(data["message"], "Test error")
        self.assertEqual(data["type"], "ValueError")
        self.assertEqual(data["url"], "http://test.com")
        self.assertIn("Traceback", data["stack_trace"])


if __name__ == "__main__":
    unittest.main()
