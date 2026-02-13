"""Context processors for the Flask application."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from firebase_admin import firestore
from flask import current_app, g

from .user import UserService

VERSION_THRESHOLD = 10
VERSION_SHORT_LENGTH = 7


def inject_global_context() -> dict[str, Any]:
    """Injects global context variables into templates."""
    # Detect version from environment variables with the following priority:
    # 1. APP_VERSION (explicitly set)
    # 2. GITHUB_SHA or GITHUB_RUN_NUMBER (GitHub Actions build)
    # 3. RENDER_GIT_COMMIT or HEROKU_SLUG_COMMIT (Git Hash from Render/Heroku)
    # 4. Fallback to "dev"
    version = (
        os.environ.get("APP_VERSION")
        or os.environ.get("GITHUB_SHA")
        or os.environ.get("GITHUB_RUN_NUMBER")
        or os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("HEROKU_SLUG_COMMIT")
    )

    if not version:
        try:
            version_file = Path(current_app.root_path).parent / "VERSION"
            if version_file.exists():
                version = version_file.read_text().strip()
        except Exception:  # nosec B110
            pass

    if not version:
        version = "dev"

    # If it's a long git hash, shorten it
    if len(version) > VERSION_THRESHOLD and version != "dev":
        version = version[:VERSION_SHORT_LENGTH]

    global_announcement = None
    try:
        db = firestore.client()
        announcement_doc = db.collection("system").document("settings").get()
        global_announcement = (
            announcement_doc.to_dict() if announcement_doc.exists else None
        )
    except Exception as e:
        current_app.logger.error(f"Error fetching global announcement: {e}")

    return {
        "current_year": datetime.now().year,
        "version": version,
        "app_version": version,
        "global_announcement": global_announcement,
        "is_testing": current_app.config.get("TESTING", False),
    }


def inject_incoming_requests_count() -> dict[str, Any]:
    """Injects incoming friend requests count into the template context."""
    try:
        user = getattr(g, "user", None)
        if user:
            db = firestore.client()
            pending_requests = UserService.get_user_pending_requests(db, user["uid"])
            return dict(
                incoming_requests_count=len(pending_requests),
                pending_friend_requests=pending_requests,
            )
    except (Exception, RuntimeError) as e:
        # Avoid logging RuntimeError as it often means we're outside a request context
        if not isinstance(e, RuntimeError):
            current_app.logger.error(f"Error fetching friend requests: {e}")
    return dict(incoming_requests_count=0, pending_friend_requests=[])


def inject_pending_tournament_invites() -> dict[str, Any]:
    """Injects pending tournament invites into the template context."""
    try:
        user = getattr(g, "user", None)
        if user:
            db = firestore.client()
            pending_invites = UserService.get_pending_tournament_invites(
                db, user["uid"]
            )
            return dict(pending_tournament_invites=pending_invites)
    except (Exception, RuntimeError) as e:
        # Avoid logging RuntimeError as it often means we're outside a request context
        if not isinstance(e, RuntimeError):
            current_app.logger.error(f"Error fetching tournament invites: {e}")
    return dict(pending_tournament_invites=[])


def inject_firebase_api_key() -> dict[str, Any]:
    """Injects the Firebase API key into the template context."""
    firebase_api_key = current_app.config.get(
        "FIREBASE_API_KEY"
    ) or current_app.config.get("GOOGLE_API_KEY")
    return dict(firebase_api_key=firebase_api_key)
