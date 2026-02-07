"""Initialize the Flask app and its extensions."""

from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, current_app, g, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

from . import admin as admin_bp
from . import auth as auth_bp
from . import error_handlers
from . import group as group_bp
from . import match as match_bp
from . import teams as teams_bp
from . import tournament as tournament_bp
from . import user as user_bp
from .extensions import csrf, login_manager, mail
from .user.helpers import smart_display_name, wrap_user
from .user.services import UserService

APP_PASSWORD_LENGTH = 16
VERSION_THRESHOLD = 10
VERSION_SHORT_LENGTH = 7


class UUIDConverter(BaseConverter):
    """URL converter for UUIDs."""

    def to_python(self, value: str) -> uuid.UUID:
        """Convert a string to a UUID."""
        return uuid.UUID(value)

    def to_url(self, value: uuid.UUID) -> str:
        """Convert a UUID to a string."""
        return str(value)


def _configure_mail_logging(app: Flask) -> None:
    """Configure detailed mail configuration logging."""
    if not app.config.get("TESTING"):
        print(
            f"DEBUG: Mail User loaded: {bool(app.config.get('MAIL_USERNAME'))}",
            file=sys.stderr,
        )
        print(
            f"DEBUG: Mail Password loaded: {bool(app.config.get('MAIL_PASSWORD'))}",
            file=sys.stderr,
        )
        pwd = app.config.get("MAIL_PASSWORD")
        if pwd and len(pwd) != APP_PASSWORD_LENGTH:
            print(
                f"DEBUG: Mail Config - Warning: Password length {len(pwd)} "
                "does not match standard App Password length.",
                file=sys.stderr,
            )


def _get_firebase_credentials(app: Flask) -> tuple[Any, str | None]:
    """Load Firebase credentials from environment, file, or defaults."""
    cred = None
    project_id = None

    cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        with suppress(json.JSONDecodeError, ValueError):
            cred_info = json.loads(cred_json)
            project_id = cred_info.get("project_id")
            cred = credentials.Certificate(cred_info)

    if not cred:
        cred_path = Path(__file__).parent.parent / "firebase_credentials.json"
        if cred_path.exists():
            with suppress(json.JSONDecodeError, ValueError):
                project_id = json.load(cred_path.open()).get("project_id")
                cred = credentials.Certificate(str(cred_path))

    if not cred:
        with suppress(Exception):
            cred = credentials.ApplicationDefault()
            project_id = os.environ.get("FIREBASE_PROJECT_ID")

    return cred, project_id


def _initialize_firebase(app: Flask) -> None:
    """Initialize Firebase Admin SDK."""
    if app.config.get("TESTING"):
        return

    cred, project_id = _get_firebase_credentials(app)

    if cred and not firebase_admin._apps:
        try:
            storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET")
            if not storage_bucket and project_id:
                storage_bucket = f"{project_id}.firebasestorage.app"

            firebase_options = {"storageBucket": storage_bucket}
            if project_id:
                firebase_options["projectId"] = project_id

            firebase_admin.initialize_app(cred, firebase_options)
        except ValueError:
            app.logger.info("Firebase app already initialized.")


def _register_blueprints(app: Flask) -> None:
    """Register all blueprints for the application."""
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(admin_bp.bp)
    app.register_blueprint(user_bp.bp)
    app.register_blueprint(match_bp.bp)
    app.register_blueprint(group_bp.bp)
    app.register_blueprint(teams_bp.bp)
    app.register_blueprint(tournament_bp.bp)
    app.register_blueprint(error_handlers.error_handlers_bp)


def _register_context_processors(app: Flask) -> None:
    """Register all context processors for the application."""

    @app.context_processor
    def inject_global_context() -> dict[str, Any]:
        version = (
            os.environ.get("APP_VERSION")
            or os.environ.get("GITHUB_RUN_NUMBER")
            or os.environ.get("RENDER_GIT_COMMIT")
            or os.environ.get("HEROKU_SLUG_COMMIT")
            or "dev"
        )
        if len(version) > VERSION_THRESHOLD and version != "dev":
            version = version[:VERSION_SHORT_LENGTH]

        return {
            "current_year": datetime.now().year,
            "version": version,
            "app_version": version,
        }

    @app.context_processor
    def inject_notifications() -> dict[str, Any]:
        if g.user:
            try:
                db = firestore.client()
                return {
                    "pending_friend_requests": UserService.get_user_pending_requests(db, g.user["uid"]),
                    "pending_tournament_invites": UserService.get_pending_tournament_invites(db, g.user["uid"])
                }
            except Exception as e:
                current_app.logger.error(f"Error fetching notifications: {e}")
        return {"pending_friend_requests": [], "pending_tournament_invites": []}


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure an instance of the Flask application."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        static_url_path="/static",
    )
    app.url_map.converters["uuid"] = UUIDConverter

    _load_app_config(app, test_config)
    _configure_mail_logging(app)
    _initialize_firebase(app)

    with suppress(OSError):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str) -> Any:
        try:
            db = firestore.client()
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                return wrap_user(user_doc.to_dict(), uid=user_id)
        except Exception as e:
            current_app.logger.error(f"Error in user_loader: {e}")
        return None

    # Register filters
    app.template_filter("smart_display_name")(smart_display_name)
    app.template_filter("display_name")(smart_display_name)

    @app.template_filter("avatar_url")
    def avatar_url_filter(user: dict[str, Any]) -> str:
        if not user:
            return ""
        wrapped = wrap_user(user)
        return wrapped.avatar_url if wrapped else ""

    _register_blueprints(app)
    app.add_url_rule("/", endpoint="auth.login", methods=["GET", "POST"])

    @app.before_request
    def load_logged_in_user() -> None:
        user_id = session.get("user_id")
        g.user = None
        if user_id:
            try:
                db = firestore.client()
                user_doc = db.collection("users").document(user_id).get()
                if user_doc.exists:
                    g.user = wrap_user(user_doc.to_dict(), uid=user_id)
                else:
                    session.clear()
            except Exception as e:
                current_app.logger.error(f"Error loading user: {e}")
                session.clear()

    _register_context_processors(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # type: ignore

    return app


def _load_app_config(app: Flask, test_config: dict[str, Any] | None) -> None:
    """Load and process application configuration."""
    def _clean(env_var):
        val = os.environ.get(env_var)
        return val.strip().replace(" ", "").strip("'").strip('"') if val else None

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev",
        FIREBASE_API_KEY=os.environ.get("FIREBASE_API_KEY"),
        GOOGLE_API_KEY=os.environ.get("GOOGLE_API_KEY"),
        MAIL_SERVER=os.environ.get("MAIL_SERVER") or "smtp.gmail.com",
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=(os.environ.get("MAIL_USE_TLS") or "true").lower() in ("true", "1", "t"),
        MAIL_USE_SSL=(os.environ.get("MAIL_USE_SSL") or "false").lower() in ("true", "1", "t"),
        MAIL_USERNAME=_clean("MAIL_USERNAME"),
        MAIL_PASSWORD=_clean("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER") or "noreply@pickaladder.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    if test_config:
        app.config.update(test_config)