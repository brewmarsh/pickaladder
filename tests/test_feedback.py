from unittest.mock import MagicMock, patch

import pytest

from pickaladder.services.feedback_service import FeedbackService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.uid = "test_user_id"
    return user


def test_submit_feedback(mock_db) -> None:
    user_id = "user123"
    feedback_type = "Bug"
    message = "Test message <script>alert('xss')</script>"

    with patch("pickaladder.services.feedback_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = MagicMock()
        feedback_id = FeedbackService.submit_feedback(
            mock_db,
            user_id,
            feedback_type,
            message,
        )

    assert feedback_id is not None
    mock_db.collection.assert_called_with("feedback")

    # Verify sanitization
    call_args = mock_db.collection().document().set.call_args[0][0]
    assert "&lt;script&gt;" in call_args["message"]
    assert call_args["userId"] == "user123"
    assert call_args["type"] == "Bug"
    assert call_args["status"] == "New"


def test_update_feedback_status(mock_db) -> None:
    feedback_id = "fb123"
    status = "In Progress"
    admin_id = "admin456"

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"userId": "user123"}
    mock_db.collection().document().get.return_value = mock_doc

    with patch(
        "pickaladder.services.notification_service.NotificationService.send_to_user",
    ) as mock_notify:
        success = FeedbackService.update_feedback_status(
            mock_db,
            feedback_id,
            status,
            admin_id,
        )

    assert success is True
    mock_db.collection().document().update.assert_called()
    update_args = mock_db.collection().document().update.call_args[0][0]
    assert update_args["status"] == "In Progress"
    assert update_args["updatedBy"] == "admin456"

    mock_notify.assert_called_once_with(
        "user123",
        "Feedback Update",
        "The status of your feedback has been updated to 'In Progress'.",
        {"type": "feedback_update", "feedback_id": "fb123"},
    )
