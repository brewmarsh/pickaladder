"""Initialize the Flask app and its extensions."""

from __future__ import annotations

import json
import os
import sys
import uuid
from contextlib import suppress
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
            print(f"DEBUG: Password length ({len(pwd)}) does not match standard ({APP_PASSWORD_LENGTH}).", file=sys.stderr)


def _get_firebase_credentials(app: Flask) -> tuple[Any, str | None]:
    """Load Firebase credentials from environment, file, or defaults."""
    cred = None
    project_id = None
    flask_env = os.environ.get("FLASK_ENV")

    # Load from Env Var
    cred_json = os.environ.get("FIREBASE_CREDENTIALS_BETA" if flask_env == "beta" else "FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        with suppress(json.JSONDecodeError, ValueError):
            cred_info = json.loads(cred_json)
            project_id = cred_info.get("project_id")
            cred = credentials.Certificate(cred_info)

    # Fallback to local File
    if not cred:
        filename = "firebase_credentials_beta.json" if flask_env == "beta" else "firebase_credentials.json"
        cred_path = Path(__file__).parent.parent / filename
        if cred_path.exists():
            with suppress(json.JSONDecodeError, ValueError):
                cred = credentials.Certificate(str(cred_path))
                with cred_path.open() as f:
                    project_id = json.load(f).get("project_id")

    # Final Fallback
    if not cred:
        with suppress(Exception):
            cred = credentials.ApplicationDefault()
            project_id = os.environ.get("FIREBASE_PROJECT_ID")

    return cred, project_id


def _initialize_firebase(app: Flask) -> None:
    """Initialize Firebase Admin SDK."""
    if app.config.get("TESTING") or firebase_admin._apps:
        return

    cred, project_id = _get_firebase_credentials(app)
    if cred:
        try:
            storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET") or f"{project_id}.firebasestorage.app"
            firebase_options = {"storageBucket": storage_bucket}
            if project_id:
                firebase_options["projectId"] = project_id
            firebase_admin.initialize_app(cred, firebase_options)
        except ValueError:
            app.logger.info("Firebase app already initialized.")


def _register_blueprints(app: Flask) -> None:
    """Register all blueprints and middleware."""
    app.register_blueprint(main_bp.bp)
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(admin_bp.bp)
    app.register_blueprint(user_bp.bp)
    app.register_blueprint(match_bp.bp)
    app.register_blueprint(group_bp.bp)
    app.register_blueprint(teams_bp.bp)
    app.register_blueprint(tournament_bp.bp)
    app.register_blueprint(error_handlers.error_handlers_bp)

    app.add_url_rule("/", endpoint="auth.login", methods=["GET", "POST"])
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


def _register_extensions(app: Flask) -> None:
    """Initialize Flask extensions and user loader."""
    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    @login_manager.user_loader
    def load_user(user_id: str) -> Any:
        impersonate_id = session.get("impersonate_id")
        id_to_load = impersonate_id if impersonate_id and session.get("is_admin") else user_id
        try:
            db = firestore.client()
            user_doc = db.collection("users").document(id_to_load).get()
            if user_doc.exists:
                return wrap_user(user_doc.to_dict(), uid=id_to_load)
        except Exception as e:
            current_app.logger.error(f"Error in user_loader: {e}")
        return None


def _register_template_utilities(app: Flask) -> None:
    """Register context processors and custom Jinja filters."""
    app.context_processor(inject_global_context)
    app.context_processor(inject_incoming_requests_count)
    app.context_processor(inject_pending_tournament_invites)
    app.context_processor(inject_firebase_api_key)

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


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True, static_folder="static")
    
    _load_config(app, test_config)
    _configure_mail_logging(app)
    _initialize_firebase(app)

    @app.before_request
    def load_logged_in_user() -> None:
        """Load user and handle impersonation logic from jules branch."""
        real_user_id = session.get("user_id")
        impersonate_id = session.get("impersonate_id")
        is_admin = session.get("is_admin", False)

        g.user = None
        g.is_impersonating = False

        if real_user_id is None:
            return

        id_to_load = impersonate_id if (impersonate_id and is_admin) else real_user_id
        if impersonate_id and is_admin:
            g.is_impersonating = True

        try:
            db = firestore.client()
            user_doc = db.collection("users").document(id_to_load).get()
            if user_doc.exists:
                g.user = wrap_user(user_doc.to_dict(), uid=id_to_load)
            elif not g.is_impersonating:
                session.clear()
            else:
                session.pop("impersonate_id", None)
                g.is_impersonating = False
        except Exception as e:
            current_app.logger.error(f"Error loading user: {e}")
            if not g.is_impersonating: session.clear()

    _register_extensions(app)
    _register_blueprints(app)
    _register_template_utilities(app)

    return app


def _load_config(app: Flask, test_config: dict[str, Any] | None) -> None:
    """Process environment variables and standard config mapping."""
    app.url_map.converters["uuid"] = UUIDConverter
    with suppress(OSError):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def clean_env(key: str) -> str | None:
        val = os.environ.get(key)
        return val.strip().replace(" ", "").strip("'").strip('"') if val else None

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev",
        FIREBASE_API_KEY=os.environ.get("FIREBASE_API_KEY"),
        GOOGLE_API_KEY=os.environ.get("GOOGLE_API_KEY"),
        MAIL_SERVER=os.environ.get("MAIL_SERVER") or "smtp.gmail.com",
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=(os.environ.get("MAIL_USE_TLS") or "true").lower() in ("true", "1", "t"),
        MAIL_USE_SSL=(os.environ.get("MAIL_USE_SSL") or "false").lower() in ("true", "1", "t"),
        MAIL_USERNAME=clean_env("MAIL_USERNAME"),
        MAIL_PASSWORD=clean_env("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER") or "noreply@pickaladder.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    if test_config:
        app.config.update(test_config)