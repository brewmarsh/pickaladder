"""Central configuration management for the application."""

import os
from datetime import timedelta


def get_env_bool(name, default="false"):
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default.lower() in ("true", "1", "t", "yes")
    return val.lower() in ("true", "1", "t", "yes")


def sanitize_cred(val):
    if val:
        return val.strip().replace(" ", "").strip("'").strip('"')
    return None


def get_env_str(name, default=None):
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val


class Config:
    """Central configuration class.

    Attributes are resolved at instantiation to allow dynamic environment overrides
    during testing while maintaining standard Flask 'from_object' compatibility.
    """

    def __init__(self):
        # Environment
        self.FLASK_ENV = get_env_str("FLASK_ENV", "development")
        self.ENV = self.FLASK_ENV

        # Security
        self.SECRET_KEY = os.environ.get("SECRET_KEY")
        if not self.SECRET_KEY and self.FLASK_ENV == "development":
            self.SECRET_KEY = "dev"

        # Firebase
        self.FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")
        self.FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
        self.FIREBASE_STORAGE_BUCKET = get_env_str(
            "FIREBASE_STORAGE_BUCKET", "pickaladder.firebasestorage.app"
        )

        # External APIs
        self.GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
        self.DUPR_API_KEY = os.environ.get("DUPR_API_KEY")
        self.DUPR_BASE_URL = get_env_str("DUPR_BASE_URL", "https://api.mydupr.com")

        # Mail
        self.MAIL_SERVER = get_env_str("MAIL_SERVER", "smtp.gmail.com")
        self.MAIL_PORT = int(get_env_str("MAIL_PORT", "587"))
        self.MAIL_USE_TLS = get_env_bool("MAIL_USE_TLS", "true")
        self.MAIL_USE_SSL = get_env_bool("MAIL_USE_SSL", "false")
        self.MAIL_USERNAME = sanitize_cred(os.environ.get("MAIL_USERNAME"))
        self.MAIL_PASSWORD = sanitize_cred(os.environ.get("MAIL_PASSWORD"))
        self.MAIL_DEFAULT_SENDER = get_env_str(
            "MAIL_DEFAULT_SENDER", "noreply@pickaladder.com"
        )

        # Session
        self.SESSION_PERMANENT = True
        self.PERMANENT_SESSION_LIFETIME = timedelta(days=31)
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
        self.SESSION_COOKIE_SECURE = self.FLASK_ENV != "development"

        # Testing
        self.TESTING = get_env_bool("TESTING", "false")
