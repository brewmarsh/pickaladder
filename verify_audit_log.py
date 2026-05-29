from unittest.mock import MagicMock

from pickaladder.admin.services import AdminService


def test_log_action() -> None:
    db = MagicMock()
    collection = db.collection.return_value
    collection.add.return_value = (None, MagicMock(id="test_log_id"))

    admin_id = "admin123"
    target_id = "user456"
    action_type = "delete_user"
    metadata = {"reason": "violation"}

    AdminService.log_action(db, admin_id, target_id, action_type, metadata)

    db.collection.assert_called_with("audit_logs")
    args, _kwargs = collection.add.call_args
    log_entry = args[0]

    assert log_entry["admin_id"] == admin_id
    assert log_entry["target_id"] == target_id
    assert log_entry["action"] == action_type
    assert log_entry["metadata"] == metadata
    assert "timestamp" in log_entry


if __name__ == "__main__":
    try:
        test_log_action()
    except Exception:
        import traceback

        traceback.print_exc()
