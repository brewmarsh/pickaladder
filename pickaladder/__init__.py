import os
import uuid
from flask import Flask, session, render_template
from flask_mail import Mail
import psycopg2
import psycopg2.extras
from werkzeug.routing import BaseConverter
from . import db
from .constants import USERS_TABLE, USER_ID

mail = Mail()


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
        UPLOAD_FOLDER="static/uploads",
    )

    # Initialize extensions
    mail.init_app(app)

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

    db.init_app(app)

    # make url_for('index') == url_for('auth.login')
    # in another app, you might define a separate main index here with
    # app.route, while giving the auth blueprint a url_prefix, but for
    # this app, the index is the login page
    app.add_url_rule("/", endpoint="auth.login")

    @app.context_processor
    def inject_user():
        if USER_ID in session:
            conn = db.get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute(
                f"SELECT * FROM {USERS_TABLE} WHERE {USER_ID} = %s", (session[USER_ID],)
            )
            user = cur.fetchone()
            cur.close()
            return dict(user=user)
        return dict(user=None)

    return app
