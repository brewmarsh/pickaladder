import os
from flask import Flask
from flask_mail import Mail

mail = Mail()

def create_app():
    """Create and configure an instance of the Flask application."""
    app = Flask(__name__, instance_relative_config=True)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Load configuration
    app.config.from_mapping(
        SECRET_KEY=os.urandom(24),
        # Default mail settings, can be overridden in config.py
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=587,
        MAIL_USE_TLS=True,
        MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
        MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
        UPLOAD_FOLDER='static/uploads',
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

    from . import db
    db.init_app(app)

    # make url_for('index') == url_for('auth.login')
    # in another app, you might define a separate main index here with
    # app.route, while giving the auth blueprint a url_prefix, but for
    # this app, the index is the login page
    app.add_url_rule("/", endpoint="auth.login")

    @app.context_processor
    def inject_user():
        if 'user_id' in session:
            conn = db.get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cur.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
            user = cur.fetchone()
            cur.close()
            return dict(user=user)
        return dict(user=None)

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('500.html'), 500

    @app.errorhandler(psycopg2.Error)
    def handle_db_error(e):
        return render_template('error.html', error=str(e)), 500

    return app
