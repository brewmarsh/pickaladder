from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

mail = Mail()
csrf = CSRFProtect()
