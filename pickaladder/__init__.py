import os
import uuid
from flask import Flask, session
from flask_mail import Mail  # type: ignore
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect  # type: ignore
from werkzeug.routing import BaseConverter
from .constants import USER_ID

db: SQLAlchemy = SQLAlchemy()
mail = Mail()
csrf = CSRFProtect()


class UUIDConverter(BaseConverter):
    def to_python(self, value):
        return uuid.UUID(value)

    def to_url(self, value):
        return str(value)


def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.url_map.converters["uuid"] = UUIDConverter

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=os.urandom(24),
        # Default mail settings, can be overridden in config.py
        MAIL_SERVER="smtp.gmail.com",
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.environ.get("MAIL_USERNAME"),
        MAIL_PASSWORD=os.environ.get("MAIL_PASSWORD"),
        MAIL_DEFAULT_SENDER="noreply@example.com",
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
    )

    db_host = os.environ.get("DB_HOST", "db")
    db_name = os.environ.get("POSTGRES_DB", "test_db")
    db_user = os.environ.get("POSTGRES_USER", "user")
    db_pass = os.environ.get("POSTGRES_PASSWORD", "password")
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize extensions
    mail.init_app(app)
    db.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from . import auth

    app.register_blueprint(auth.bp)

    from . import admin

    app.register_blueprint(admin.bp)

    from . import user

    app.register_blueprint(user.bp)

    from . import match

    app.register_blueprint(match.bp)

    from . import error_handlers

    app.register_blueprint(error_handlers.error_handlers_bp)

    # make url_for('index') == url_for('auth.login')
    # in another app, you might define a separate main index here with
    # app.route, while giving the auth blueprint a url_prefix, but for
    # this app, the index is the login page
    app.add_url_rule("/", endpoint="auth.login")

    @app.context_processor
    def inject_user():
        if USER_ID in session:
            # This will be refactored to use the ORM in a later step
            from .models import User

            user = User.query.get(session[USER_ID])
            return dict(user=user)
        return dict(user=None)

    return app
