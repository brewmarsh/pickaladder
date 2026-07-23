"""Service layer for admin-related operations."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_admin import firestore


class AdminService:
    """Service class for admin-related operations."""

    @staticmethod
    def get_admin_stats(db: firestore.Client) -> dict[str, Any]:
        """Fetch high-level stats for the admin dashboard.

        Uses efficient count aggregations concurrently.
        """
        import concurrent.futures

        def get_total_users() -> int:
            return db.collection("users").count().get()[0][0].value

        def get_active_tournaments() -> int:
            return (
                db.collection("tournaments")
                .where(filter=firestore.FieldFilter("status", "!=", "Completed"))
                .count()
                .get()[0][0]
                .value
            )

        def get_recent_matches() -> int:
            yesterday = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(
                days=1,
            )
            return (
                db.collection("matches")
                .where(filter=firestore.FieldFilter("createdAt", ">=", yesterday))
                .count()
                .get()[0][0]
                .value
            )

        # ⚡ Bolt Optimization:
        # What: Execute independent database count queries concurrently instead of sequentially.
        # Why: Resolves an N+1 latency bottleneck where each query waits for the previous one to complete.
        # Impact: Expected to reduce total latency for this aggregation block by ~2-3x.
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            total_users_future = executor.submit(get_total_users)
            active_tournaments_future = executor.submit(get_active_tournaments)
            recent_matches_future = executor.submit(get_recent_matches)

            total_users = total_users_future.result()
            active_tournaments = active_tournaments_future.result()
            recent_matches = recent_matches_future.result()

        return {
            "total_users": total_users,
            "active_tournaments": active_tournaments,
            "recent_matches": recent_matches,
        }

    @staticmethod
    def toggle_setting(db: firestore.Client, setting_key: str) -> bool:
        """Toggle a boolean setting in the Firestore 'settings' collection."""
        setting_ref = db.collection("settings").document(setting_key)
        setting = setting_ref.get()
        current_value = (
            setting.to_dict().get("value", False) if setting.exists else False
        )
        not_current_value = not current_value
        setting_ref.set({"value": not_current_value})
        return not_current_value

    @staticmethod
    def delete_user(db: firestore.Client, user_id: str) -> None:
        """Delete a user from Firebase Auth and Firestore."""
        from firebase_admin import auth  # noqa: PLC0415

        # Delete from Firebase Auth
        auth.delete_user(user_id)
        # Delete from Firestore
        db.collection("users").document(user_id).delete()

    @staticmethod
    def delete_user_data(db: firestore.Client, uid: str) -> None:
        """Delete a user from Firestore and Firebase Auth."""
        from firebase_admin import auth  # noqa: PLC0415

        # Delete from Firestore
        db.collection("users").document(uid).delete()
        # Delete from Firebase Auth
        try:
            auth.delete_user(uid)
        except Exception:  # nosec B110
            # If user not found in Auth, we still want to proceed
            pass

    @staticmethod
    def build_friend_graph(db: firestore.Client) -> dict[str, Any]:
        """Build a dictionary representing the social graph of users and friendships."""
        users_stream = db.collection("users").stream()
        nodes = []
        user_ids = set()

        for user_doc in users_stream:
            data = user_doc.to_dict()
            nodes.append(
                {"id": user_doc.id, "label": data.get("username") or user_doc.id},
            )
            user_ids.add(user_doc.id)

        edges = []
        # Optimization: Use collection_group to fetch all accepted friendships
        # in a single query instead of one query per user.
        # Friendships are reciprocal.
        friends_stream = (
            db.collection_group("friends")
            .where(filter=firestore.FieldFilter("status", "==", "accepted"))
            .stream()
        )
        for friend_doc in friends_stream:
            # friend_doc.reference is users/{uid}/friends/{friend_id}
            # so parent.parent gives us the user document.
            uid = friend_doc.reference.parent.parent.id
            if uid < friend_doc.id:  # Avoid duplicate edges
                edges.append({"from": uid, "to": friend_doc.id})

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def promote_user(db: firestore.Client, user_id: str) -> str:
        """Promote a user to admin status in Firestore."""
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"isAdmin": True})
        return user_ref.get().to_dict().get("username", "user")

    @staticmethod
    def verify_user(db: firestore.Client, user_id: str) -> None:
        """Manually verify a user's email in Auth and Firestore."""
        from firebase_admin import auth  # noqa: PLC0415

        auth.update_user(user_id, email_verified=True)
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"email_verified": True})

    @staticmethod
    def get_recent_audit_logs(
        db: firestore.Client,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Fetch recent administrative actions."""
        docs = (
            db.collection("audit_logs")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        logs = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            logs.append(data)
        return logs

    @staticmethod
    def get_growth_metrics(db: firestore.Client) -> dict[str, Any]:
        """Calculate user signups per day for the last 7 days."""
        import concurrent.futures

        now = datetime.datetime.now(datetime.timezone.utc)

        def fetch_count_for_day(days_ago: int) -> tuple[int, str, int]:
            day = now - datetime.timedelta(days=days_ago)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + datetime.timedelta(days=1)

            count = (
                db.collection("users")
                .where(filter=firestore.FieldFilter("createdAt", ">=", day_start))
                .where(filter=firestore.FieldFilter("createdAt", "<", day_end))
                .count()
                .get()[0][0]
                .value
            )
            return days_ago, day.strftime("%b %d"), count

        # ⚡ Bolt Optimization:
        # What: Execute independent database count queries concurrently instead of sequentially.
        # Why: Resolves an N+1 latency bottleneck where each query waits for the previous one to complete.
        # Impact: Expected to reduce total latency for this aggregation block by ~5-7x.
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
            futures = [
                executor.submit(fetch_count_for_day, i) for i in range(6, -1, -1)
            ]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Sort results by days_ago descending (which means oldest first, 6 to 0)
        results.sort(key=lambda x: x[0], reverse=True)

        labels = [res[1] for res in results]
        values = [res[2] for res in results]

        return {"labels": labels, "values": values}

    @staticmethod
    def log_action(
        db: firestore.Client,
        admin_id: str,
        target_id: str | None,
        action_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Log an administrative action to the audit_logs collection."""
        log_entry = {
            "admin_id": admin_id,
            "target_id": target_id,
            "action": action_type,
            "metadata": metadata or {},
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
        _, doc_ref = db.collection("audit_logs").add(log_entry)
        return doc_ref.id
