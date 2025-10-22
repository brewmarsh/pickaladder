import os
import uuid
from flask import Flask, session, g, current_app
from werkzeug.routing import BaseConverter
from .extensions import mail, csrf
import firebase_admin
from firebase_admin import credentials, firestore


class UUIDConverter(BaseConverter):
    def to_python(self, value):
        return uuid.UUID(value)

    def to_url(self, value):
        return str(value)


def create_app(test_config=None):
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.url_map.converters["uuid"] = UUIDConverter

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=os.urandom(24),
        # Default mail settings, can be overridden in config.py
        MAIL_SERVER=os.environ.get("MAIL_SERVER", "smtp.gmail.com"),
        MAIL_PORT=int(os.environ.get("MAIL_PORT") or 587),
        MAIL_USE_TLS=os.environ.get("MAIL_USE_TLS", "true").lower()
        in ["true", "1", "t"],
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER=os.environ.get(
            "MAIL_DEFAULT_SENDER", "noreply@pickaladder.com"
        ),
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    if test_config:
        app.config.update(test_config)

    # Initialize Firebase Admin SDK only if not in testing mode
    if not app.config.get("TESTING"):
        # The GOOGLE_APPLICATION_CREDENTIALS environment variable should be set to the
        # path of the service account key file.
        try:
            # When running in a Google Cloud environment, the credentials are
            # automatically discovered.
            cred = credentials.ApplicationDefault()
        except Exception:
            cred = None  # Handle cases where default creds are not found

        try:
            firebase_admin.initialize_app(
                cred,
                {
                    "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
                    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
                },
            )
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

    return app
