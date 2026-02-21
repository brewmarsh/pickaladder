"""Initialize the Flask app and its extensions."""

from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import suppress
from datetime import timedelta
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, credentials, firestore
from flask import Flask, current_app, g, request, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

from . import admin as admin_bp
from . import auth as auth_bp
from . import error_handlers
from . import group as group_bp
from . import main as main_bp
from . import match as match_bp
from . import teams as teams_bp
from . import tournament as tournament_bp
from . import user as user_bp
from .context_processors import (
    inject_firebase_api_key,
    inject_global_context,
    inject_incoming_requests_count,
    inject_pending_tournament_invites,
)
from .extensions import csrf, login_manager, mail
from .user.helpers import smart_display_name, wrap_user

APP_PASSWORD_LENGTH = 16


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
        print(f"DEBUG: Mail User loaded: {bool(app.config.get('MAIL_USERNAME'))}", file=sys.stderr)
        print(f"DEBUG: Mail Password loaded: {bool(app.config.get('MAIL_PASSWORD'))}", file=sys.stderr)
        print(f"DEBUG: Mail Config - Server: {app.config.get('MAIL_SERVER')}", file=sys.stderr)
        
        pwd = app.config.get("MAIL_PASSWORD")
        if pwd and len(pwd) != APP_PASSWORD_LENGTH:
             print(f"DEBUG: Mail Config - Password Length ({len(pwd)}) DOES NOT match App Password standard.", file=sys.stderr)


def _get_firebase_credentials(app: Flask) -> tuple[Any, str | None]:
    """Load Firebase credentials from environment, file, or defaults."""
    cred = None
    project_id = None
    flask_env = os.environ.get("FLASK_ENV")

    if flask_env == "beta":
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_BETA")
    else:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")

    if cred_json:
        with suppress(json.JSONDecodeError, ValueError):
            cred_info = json.loads(cred_json)
            project_id = cred_info.get("project_id")
            cred = credentials.Certificate(cred_info)

    if not cred:
        if flask_env == "beta":
            cred_path = Path(__file__).parent.parent / "firebase_credentials_beta.json"
        else:
            cred_path = Path(__file__).parent.parent / "firebase_credentials.json"

        if cred_path.exists():
            with suppress(json.JSONDecodeError, ValueError):
                with cred_path.open() as f:
                    cred_info = json.load(f)
                    project_id = cred_info.get("project_id")
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
    app.register_blueprint(main_bp.bp)
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
    app.context_processor(inject_global_context)
    app.context_processor(inject_incoming_requests_count)
    app.context_processor(inject_pending_tournament_invites)
    app.context_processor(inject_firebase_api_key)


def _load_app_config(app: Flask, test_config: dict[str, Any] | None) -> None:
    """Load and process application configuration with robust session handling."""
    mail_username = os.environ.get("MAIL_USERNAME")
    if mail_username:
        mail_username = mail_username.strip().replace(" ", "").strip("'").strip('"')

    mail_password = os.environ.get("MAIL_PASSWORD")
    if mail_password:
        mail_password = mail_password.strip().replace(" ", "").strip("'").strip('"')

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev",
        FLASK_ENV=os.environ.get("FLASK_ENV", "development"),
        FIREBASE_API_KEY=os.environ.get("FIREBASE_API_KEY"),
        GOOGLE_API_KEY=os.environ.get("GOOGLE_API_KEY"),
        MAIL_SERVER=os.environ.get("MAIL_SERVER") or "smtp.gmail.com",
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=(os.environ.get("MAIL_USE_TLS") or "true").lower() in ("true", "1", "t"),
        MAIL_USE_SSL=(os.environ.get("MAIL_USE_SSL") or "false").lower() in ("true", "1", "t"),
        MAIL_USERNAME=mail_username,
        MAIL_PASSWORD=mail_password,
        MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER") or "noreply@pickaladder.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        
        # Merged Session Configuration
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(days=31),
        REMEMBER_COOKIE_DURATION=timedelta(days=31),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") != "development",
    )

    if test_config:
        app.config.update(test_config)


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

    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str) -> Any:
        impersonate_id = session.get("impersonate_id")
        is_admin = session.get("is_admin", False)
        id_to_load = impersonate_id if (impersonate_id and is_admin) else user_id

        try:
            db = firestore.client()
            user_doc = db.collection("users").document(id_to_load).get()
            if user_doc.exists:
                return wrap_user(user_doc.to_dict(), uid=id_to_load)
        except Exception as e:
            current_app.logger.error(f"Error in user_loader: {e}")
        return None

    app.template_filter("smart_display_name")(smart_display_name)
    app.template_filter("display_name")(smart_display_name)

    @app.template_filter("avatar_url")
    def avatar_url_filter(user: dict[str, Any]) -> str:
        if not user: return ""
        wrapped = wrap_user(user)
        url = wrapped.avatar_url if wrapped else ""
        if url == "default":
            seed = user.get("username") or user.get("email") or "User"
            return f"https://api.dicebear.com/9.x/avataaars/svg?seed={seed}"
        return url

    @app.template_filter("pluralize")
    def pluralize_filter(number: int, singular: str = "", plural: str | None = None) -> str:
        if number == 1: return singular
        return plural if plural is not None else f"{singular}s"

    _register_blueprints(app)
    app.add_url_rule("/", endpoint="auth.login", methods=["GET", "POST"])

    @app.before_request
    def load_logged_in_user() -> None:
        uid = session.get("user_id")
        if not uid:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                id_token = auth_header[7:].strip()
                try:
                    decoded_token = auth.verify_id_token(id_token)
                    uid = decoded_token["uid"]
                    session["user_id"] = uid
                    session.permanent = True
                except Exception as e:
                    app.logger.debug(f"Token verification failed: {e}")

        g.user = None
        g.is_impersonating = False
        if not uid: return

        impersonate_id = session.get("impersonate_id")
        is_admin = session.get("is_admin", False)
        id_to_load = uid

        if impersonate_id and is_admin:
            id_to_load = impersonate_id
            g.is_impersonating = True

        try:
            db = firestore.client()
            user_doc = db.collection("users").document(id_to_load).get()
            if user_doc.exists:
                g.user = wrap_user(user_doc.to_dict(), uid=id_to_load)
                if not g.is_impersonating:
                    session["is_admin"] = g.user.get("isAdmin", False)
            elif not g.is_impersonating:
                session.clear()
            else:
                session.pop("impersonate_id", None)
                g.is_impersonating = False
        except Exception as e:
            app.logger.error(f"Error loading user {id_to_load}: {e}")
            if not g.is_impersonating: session.clear()

    _register_context_processors(app)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1) # type: ignore
    return app