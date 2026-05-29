"""Service for sending push notifications via FCM."""

from __future__ import annotations

from firebase_admin import firestore, messaging
from flask import current_app

from pickaladder.extensions import executor


class NotificationService:
    """Service for handling push notifications."""

    @staticmethod
    def send_push_notification_now(
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> str | None:
        """Send a push notification to a specific token synchronously.

        This method should be called within a background thread.
        """
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            token=token,
        )
        try:
            response = messaging.send(message)
            current_app.logger.info(f"Successfully sent FCM message: {response}")
            return response
        except Exception as e:
            current_app.logger.exception(f"Error sending FCM message: {e!s}")
            return None

    @staticmethod
    def send_push_notification(
        token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        """Send a push notification asynchronously."""
        executor.run_async(
            NotificationService.send_push_notification_now,
            token=token,
            title=title,
            body=body,
            data=data,
        )

    @staticmethod
    def send_to_user_now(
        user_id: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        """Fetch user FCM token and send notification synchronously.

        This method should be called within a background thread.
        """
        db = firestore.client()
        user_doc = db.collection("users").document(user_id).get()

        if not user_doc.exists:
            current_app.logger.warning(f"User {user_id} not found for notification")
            return

        user_data = user_doc.to_dict()
        if not user_data:
            return

        token = user_data.get("fcmToken")
        if not token:
            current_app.logger.debug(
                f"User {user_id} has no fcmToken, skipping notification",
            )
            return

        NotificationService.send_push_notification_now(token, title, body, data)

    @staticmethod
    def send_to_user(
        user_id: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> None:
        """Fetch user FCM token and send notification asynchronously."""
        executor.run_async(
            NotificationService.send_to_user_now,
            user_id=user_id,
            title=title,
            body=body,
            data=data,
        )
