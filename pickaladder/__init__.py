"""Initialize the Flask app and its extensions."""

import os
import uuid

import firebase_admin
from firebase_admin import credentials, firestore
from flask import Flask, current_app, g, session
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import BaseConverter

from .extensions import csrf, mail


class UUIDConverter(BaseConverter):
    """URL converter for UUIDs."""

    def to_python(self, value):
        """Convert a string to a UUID."""
        return uuid.UUID(value)

    def to_url(self, value):
        """Convert a UUID to a string."""
        return str(value)


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
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or "dev",
        # Default mail settings, can be overridden in config.py
        MAIL_SERVER=os.environ.get("MAIL_SERVER") or "smtp.gmail.com",
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=(os.environ.get("MAIL_USE_TLS") or "true").lower()
        in ["true", "1", "t"],
        MAIL_USE_SSL=(os.environ.get("MAIL_USE_SSL") or "false").lower()
        in ["true", "1", "t"],
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.environ.get("MAIL_DEFAULT_SENDER")
        or "noreply@pickaladder.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    if test_config:
        app.config.update(test_config)

    # Initialize Firebase Admin SDK only if not in testing mode
    if not app.config.get("TESTING"):
        cred = None
        project_id = None
        cred_info = {}

        # First, try to load from environment variable (for production)
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            import json

            try:
                cred_info = json.loads(cred_json)
                project_id = cred_info.get("project_id")
                cred = credentials.Certificate(cred_info)
            except (json.JSONDecodeError, ValueError) as e:
                app.logger.error(f"Error parsing FIREBASE_CREDENTIALS_JSON: {e}")

        # If env var fails or is not present, try loading from file (for local dev)
        if not cred:
            cred_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "firebase_credentials.json"
            )
            if os.path.exists(cred_path):
                import json

                try:
                    with open(cred_path, "r") as f:
                        cred_info = json.load(f)
                    project_id = cred_info.get("project_id")
                    cred = credentials.Certificate(cred_path)
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

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize extensions
    mail.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from . import auth as auth_bp

    app.register_blueprint(auth_bp.bp)

    from . import admin as admin_bp

    app.register_blueprint(admin_bp.bp)

    from . import user as user_bp

    app.register_blueprint(user_bp.bp)

    from . import match as match_bp

    app.register_blueprint(match_bp.bp)

    from . import group as group_bp

    app.register_blueprint(group_bp.bp)

    from . import error_handlers

    app.register_blueprint(error_handlers.error_handlers_bp)

    # make url_for('index') == url_for('auth.login')
    # in another app, you might define a separate main index here with
    # app.route, while giving the auth blueprint a url_prefix, but for
    # this app, the index is the login page
    app.add_url_rule("/", endpoint="auth.login", methods=["GET", "POST"])

    @app.before_request
    def load_logged_in_user():
        """If a user_id is in the session, load the user data from Firestore and store it in g."""
        user_id = session.get("user_id")
        g.user = None
        if user_id is None:
            return

        try:
            db = firestore.client()
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                g.user = user_doc.to_dict()
                g.user["uid"] = user_id  # Ensure uid is in the user object
            else:
                # User ID in session but no user in DB. Clear the session.
                session.clear()
                current_app.logger.warning(
                    f"User {user_id} in session but not found in Firestore."
                )
        except Exception as e:
            current_app.logger.error(f"Error loading user from session: {e}")
            session.clear()  # Clear session on error to be safe

    @app.context_processor
    def inject_version():
        """Injects the application version into the template context."""
        return dict(app_version=os.environ.get("APP_VERSION", "dev"))

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    return app
