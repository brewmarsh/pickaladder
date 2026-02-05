"""Initialize the Flask app and its extensions."""

import json
import os
import sys
import uuid
from contextlib import suppress
from pathlib import Path

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
from .extensions import csrf, mail
from .user.utils import UserService, smart_display_name, wrap_user

APP_PASSWORD_LENGTH = 16


class UUIDConverter(BaseConverter):
    """URL converter for UUIDs."""

    # TODO: Add type hints for Agent clarity
    def to_python(self, value):
        """Convert a string to a UUID."""
        return uuid.UUID(value)

    # TODO: Add type hints for Agent clarity
    def to_url(self, value):
        """Convert a UUID to a string."""
        return str(value)


def _configure_mail_logging(app):
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
        print(
            f"DEBUG: Mail Config - User: {app.config.get('MAIL_USERNAME')}",
            file=sys.stderr,
        )
        print(
            f"DEBUG: Mail Config - Server: {app.config.get('MAIL_SERVER')}",
            file=sys.stderr,
        )
        print(
            f"DEBUG: Mail Config - Port: {app.config.get('MAIL_PORT')}", file=sys.stderr
        )
        print(
            f"DEBUG: Mail Config - TLS: {app.config.get('MAIL_USE_TLS')}",
            file=sys.stderr,
        )
        print(
            f"DEBUG: Mail Config - SSL: {app.config.get('MAIL_USE_SSL')}",
            file=sys.stderr,
        )
        pwd = app.config.get("MAIL_PASSWORD")
        if pwd:
            print(
                f"DEBUG: Mail Config - Password Length: {len(pwd)}",
                file=sys.stderr,
            )
            if len(pwd) == APP_PASSWORD_LENGTH:
                print(
                    "DEBUG: Password length matches standard App Password length "
                    f"({APP_PASSWORD_LENGTH}).",
                    file=sys.stderr,
                )
            else:
                print(
                    "DEBUG: Password length DOES NOT match standard App Password "
                    f"length ({APP_PASSWORD_LENGTH}). Possible regular password used?",
                    file=sys.stderr,
                )
        else:
            print("DEBUG: Mail Config - No Password set!", file=sys.stderr)


def _initialize_firebase(app):
    """Initialize Firebase Admin SDK."""
    if not app.config.get("TESTING"):
        cred = None
        project_id = None
        cred_info = {}

        # First, try to load from environment variable (for production)
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                cred_info = json.loads(cred_json)
                project_id = cred_info.get("project_id")
                cred = credentials.Certificate(cred_info)
            except (json.JSONDecodeError, ValueError) as e:
                app.logger.error(f"Error parsing FIREBASE_CREDENTIALS_JSON: {e}")

        # If env var fails or is not present, try loading from file (for local dev)
        if not cred:
            cred_path = Path(__file__).parent.parent / "firebase_credentials.json"
            if cred_path.exists():
                try:
                    with cred_path.open() as f:
                        cred_info = json.load(f)
                    project_id = cred_info.get("project_id")
                    cred = credentials.Certificate(str(cred_path))
                except (json.JSONDecodeError, ValueError) as e:
                    app.logger.error(f"Error loading credentials from file: {e}")

        # If both methods fail, fallback to default credentials
        if not cred:
            try:
                cred = credentials.ApplicationDefault()
                project_id = os.environ.get("FIREBASE_PROJECT_ID")
            except Exception as e:
                app.logger.error(
                    f"Could not find any valid credentials (env, file, or default): {e}"
                )

        # Initialize the app if credentials were found
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
                # This can happen if the app is already initialized, which is fine.
                app.logger.info("Firebase app already initialized.")


# TODO: Add type hints for Agent clarity
def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(
        __name__,
        instance_relative_config=True,
        static_folder="static",
        static_url_path="/static",
    )
    app.url_map.converters["uuid"] = UUIDConverter

    # Load configuration
    mail_username = os.environ.get("MAIL_USERNAME")
    if mail_username:
        # Emails shouldn't have spaces. Remove them to handle copy-paste
        # errors or quotes with spaces.
        mail_username = mail_username.strip().replace(" ", "").strip("'").strip('"')

    mail_password = os.environ.get("MAIL_PASSWORD")
    if mail_password:
        # Google App Passwords are often displayed with spaces, which smtplib/gmail
        # doesn't like. We also strip quotes to handle cases where users wrap the
        # password in quotes in their env vars.
        mail_password = mail_password.strip().replace(" ", "").strip("'").strip('"')

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev",
        FIREBASE_API_KEY=os.environ.get("FIREBASE_API_KEY"),
        GOOGLE_API_KEY=os.environ.get("GOOGLE_API_KEY"),
        # Default mail settings, can be overridden in config.py
        MAIL_SERVER=os.environ.get("MAIL_SERVER") or "smtp.gmail.com",
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=(os.environ.get("MAIL_USE_TLS") or "true").lower()
        in ("true", "1", "t"),
        MAIL_USE_SSL=(os.environ.get("MAIL_USE_SSL") or "false").lower()
        in ("true", "1", "t"),
        MAIL_USERNAME=mail_username,
        MAIL_PASSWORD=mail_password,
        MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER")
        or "noreply@pickaladder.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    _configure_mail_logging(app)

    if test_config:
        app.config.update(test_config)

    _initialize_firebase(app)

    # Ensure the instance folder exists
    with suppress(OSError):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Initialize extensions
    mail.init_app(app)
    csrf.init_app(app)

    # Register filters
    app.template_filter("smart_display_name")(smart_display_name)

    @app.template_filter("avatar_url")
    def avatar_url_filter(user):
        """Return the avatar URL for a user."""
        if not user:
            return ""
        wrapped = wrap_user(user)
        return wrapped.avatar_url

    # Register blueprints
    app.register_blueprint(auth_bp.bp)
    app.register_blueprint(admin_bp.bp)
    app.register_blueprint(user_bp.bp)
    app.register_blueprint(match_bp.bp)
    app.register_blueprint(group_bp.bp)
    app.register_blueprint(teams_bp.bp)
    app.register_blueprint(tournament_bp.bp)
    app.register_blueprint(error_handlers.error_handlers_bp)

    # make url_for('index') == url_for('auth.login')
    # in another app, you might define a separate main index here with
    # app.route, while giving the auth blueprint a url_prefix, but for
    # this app, the index is the login page
    app.add_url_rule("/", endpoint="auth.login", methods=["GET", "POST"])

    # TODO: Add type hints for Agent clarity
    @app.before_request
    def load_logged_in_user():
        """Load user from session.

        If a user_id is in the session, load the user data from Firestore and
        store it in g.
        """
        user_id = session.get("user_id")
        g.user = None
        if user_id is None:
            return

        try:
            db = firestore.client()
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                g.user = wrap_user(user_doc.to_dict(), uid=user_id)
            else:
                # User ID in session but no user in DB. Clear the session.
                session.clear()
                current_app.logger.warning(
                    f"User {user_id} in session but not found in Firestore."
                )
        except Exception as e:
            current_app.logger.error(f"Error loading user from session: {e}")
            session.clear()  # Clear session on error to be safe

    # TODO: Add type hints for Agent clarity
    @app.context_processor
    def inject_version():
        """Injects the application version into the template context."""
        return dict(app_version=os.environ.get("APP_VERSION", "dev"))

    # TODO: Add type hints for Agent clarity
    @app.context_processor
    def inject_pending_tournament_invites():
        """Injects pending tournament invites into the template context."""
        if g.user:
            try:
                db = firestore.client()
                pending_invites = UserService.get_pending_tournament_invites(
                    db, g.user["uid"]
                )
                return dict(pending_tournament_invites=pending_invites)
            except Exception as e:
                current_app.logger.error(f"Error fetching tournament invites: {e}")
        return dict(pending_tournament_invites=[])

    @app.context_processor
    def inject_firebase_api_key():
        """Injects the Firebase API key into the template context."""
        firebase_api_key = current_app.config.get(
            "FIREBASE_API_KEY"
        ) or current_app.config.get("GOOGLE_API_KEY")
        return dict(firebase_api_key=firebase_api_key)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app
