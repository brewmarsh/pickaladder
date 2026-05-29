from unittest.mock import MagicMock, patch

from flask import Flask, g

from pickaladder.admin.routes import (
    admin_delete_match,
    admin_delete_user,
    announcement,
    promote_user,
)


def test_admin_logs() -> None:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"

    with app.test_request_context(
        method="POST",
        data={"announcement_text": "test", "level": "info"},
    ):
        g.user = MagicMock(uid="admin_uid")
        from flask import session

        session["is_admin"] = True
        with (
            patch("pickaladder.admin.routes.firestore.client") as mock_firestore,
            patch("pickaladder.admin.routes.AdminService.log_action") as mock_log,
            patch("pickaladder.admin.routes.url_for", return_value="/admin"),
            patch("pickaladder.admin.routes.flash"),
        ):
            # Test announcement
            announcement()
            mock_log.assert_any_call(
                mock_firestore(),
                "admin_uid",
                None,
                "update_announcement",
                {"text": "test", "active": False, "level": "info"},
            )

    with app.test_request_context(method="POST"):
        g.user = MagicMock(uid="admin_uid")
        session["is_admin"] = True
        with (
            patch("pickaladder.admin.routes.firestore.client") as mock_firestore,
            patch("pickaladder.admin.routes.AdminService.log_action") as mock_log,
            patch("pickaladder.admin.routes.url_for", return_value="/admin"),
            patch("pickaladder.admin.routes.flash"),
        ):
            # Test delete match
            admin_delete_match("match_123")
            mock_log.assert_any_call(
                mock_firestore(),
                "admin_uid",
                "match_123",
                "delete_match",
            )

    with app.test_request_context(method="POST", data={"user_identifier": "user_123"}):
        g.user = MagicMock(uid="admin_uid")
        session["is_admin"] = True
        with (
            patch("pickaladder.admin.routes.firestore.client") as mock_firestore,
            patch("pickaladder.admin.routes.AdminService.log_action") as mock_log,
            patch(
                "pickaladder.admin.routes._lookup_user_by_identifier",
                return_value=("user_123", "test@example.com"),
            ),
            patch("pickaladder.admin.routes.AdminService.delete_user"),
            patch("pickaladder.admin.routes.url_for", return_value="/admin"),
            patch("pickaladder.admin.routes.flash"),
        ):
            # Test delete user (via admin_delete_user -> _perform_user_deletion)
            admin_delete_user()
            mock_log.assert_any_call(
                mock_firestore(),
                "admin_uid",
                "user_123",
                "delete_user",
                {"email": "test@example.com"},
            )

    with app.test_request_context(method="POST"):
        g.user = MagicMock(uid="admin_uid")
        session["is_admin"] = True
        with (
            patch("pickaladder.admin.routes.firestore.client") as mock_firestore,
            patch("pickaladder.admin.routes.AdminService.log_action") as mock_log,
            patch(
                "pickaladder.admin.routes.AdminService.promote_user",
                return_value="Test User",
            ),
            patch("pickaladder.admin.routes.url_for", return_value="/admin"),
            patch("pickaladder.admin.routes.flash"),
        ):
            # Test promote user
            promote_user("user_123")
            mock_log.assert_any_call(
                mock_firestore(),
                "admin_uid",
                "user_123",
                "promote_user",
            )


if __name__ == "__main__":
    try:
        test_admin_logs()
    except Exception:
        import traceback

        traceback.print_exc()
