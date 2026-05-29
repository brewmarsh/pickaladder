import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.services.error_service import ErrorService


class ErrorPersistenceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(
            {"TESTING": True, "SECRET_KEY": "test", "WTF_CSRF_ENABLED": False},
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.req_context = self.app.test_request_context()
        self.req_context.push()
        self.db = MagicMock()

    def tearDown(self) -> None:
        self.req_context.pop()
        self.app_context.pop()

    @patch("pickaladder.services.error_service.firestore")
    @patch("pickaladder.services.error_service.request")
    def test_log_error_persists_to_firestore(
        self, mock_request, mock_firestore
    ) -> None:
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
            msg = "Test error"
            raise ValueError(msg)
        except ValueError as e:
            error_id = ErrorService.log_error(e)

        assert error_id == "error123"
        self.db.collection.assert_called_with("system_errors")

        # Verify data sent to Firestore
        args, _kwargs = mock_coll.add.call_args
        data = args[0]
        assert data["message"] == "Test error"
        assert data["type"] == "ValueError"
        assert data["url"] == "http://test.com"
        assert "Traceback" in data["stack_trace"]


if __name__ == "__main__":
    unittest.main()
