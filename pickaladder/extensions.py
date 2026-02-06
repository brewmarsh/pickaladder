"""Flask extensions for the application."""

from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()
