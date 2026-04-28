"""Flask extensions for the application."""

from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from pickaladder.core.tasks import TaskExecutor

mail = Mail()
csrf = CSRFProtect()
login_manager = LoginManager()
executor = TaskExecutor()
