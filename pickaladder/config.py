"""Central configuration management for the application."""

import os
from datetime import timedelta
from typing import Optional


class Config:
    """Central configuration class."""

    # Environment
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    ENV = FLASK_ENV  # Compatibility with older Flask patterns

    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY and FLASK_ENV == "development":
        SECRET_KEY = "dev"

    # Firebase
    FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")
    FIREBASE_PROJECT_ID = os.environ.get("FIREBASE_PROJECT_ID")
    FIREBASE_STORAGE_BUCKET = (
        os.environ.get("FIREBASE_STORAGE_BUCKET") or "pickaladder.firebasestorage.app"
    )

    # External APIs
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

    # Mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER") or "smtp.gmail.com"
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 587)
    MAIL_USE_TLS = (os.environ.get("MAIL_USE_TLS") or "true").lower() in ("true", "1", "t")
    MAIL_USE_SSL = (os.environ.get("MAIL_USE_SSL") or "false").lower() in (
        "true",
        "1",
        "t",
    )

    # Strip whitespace and quotes from mail credentials if present
    _mail_username = os.environ.get("MAIL_USERNAME")
    MAIL_USERNAME = (
        _mail_username.strip().replace(" ", "").strip("'").strip('"')
        if _mail_username
        else None
    )

    _mail_password = os.environ.get("MAIL_PASSWORD")
    MAIL_PASSWORD = (
        _mail_password.strip().replace(" ", "").strip("'").strip('"')
        if _mail_password
        else None
    )

    MAIL_DEFAULT_SENDER = (
        os.environ.get("MAIL_DEFAULT_SENDER") or "noreply@pickaladder.com"
    )

    # Session
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FLASK_ENV != "development"
