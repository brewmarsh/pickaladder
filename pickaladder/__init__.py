import os
from datetime import datetime, timedelta
from flask import Flask
from flask_login import LoginManager
from google.cloud import firestore

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    
    # Initialize Firestore
    db = firestore.client()

    # Configure Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # Remember Me cookie duration (30 days)
    app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.get(user_id)
    
    # Context processor to inject variables into all templates
    @app.context_processor
    def inject_global_context():
        # Version Waterfall Logic
        version = os.environ.get("APP_VERSION") or \
                  os.environ.get("GITHUB_RUN_NUMBER") or \
                  os.environ.get("RENDER_GIT_COMMIT") or \
                  "dev"
        
        # If it's a long git hash, shorten it
        if len(version) > 10 and version != "dev":
            version = version[:7]

        return {
            "current_year": datetime.now().year,
            "version": version,
        }

    # Blueprint Registrations
    from .auth.routes import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from .user.routes import user as user_blueprint
    app.register_blueprint(user_blueprint, url_prefix='/user')

    from .group.routes import group as group_blueprint
    app.register_blueprint(group_blueprint, url_prefix='/group')

    from .match.routes import match as match_blueprint
    app.register_blueprint(match_blueprint, url_prefix='/match')
    
    from .admin.routes import admin as admin_blueprint
    app.register_blueprint(admin_blueprint, url_prefix='/admin')

    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            return redirect(url_for('user.dashboard'))
        return redirect(url_for('auth.login'))

    return app