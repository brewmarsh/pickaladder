"""Structured logging utility for pickaladder."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from flask import Flask, request


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs JSON strings for production logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON."""
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add Flask request context if available
        try:
            if request:
                log_data["path"] = request.path
                log_data["method"] = request.method
                log_data["remote_addr"] = request.remote_addr
        except RuntimeError:
            # Outside of request context
            pass

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(app: Flask) -> None:
    """Configure structured logging for the Flask application."""
    # Prevent duplicate handlers
    if getattr(app, "_logging_setup_done", False):
        return

    env = app.config.get("ENV", "development")
    log_level = logging.DEBUG if env == "development" else logging.INFO

    # Set root logger level
    logging.getLogger().setLevel(log_level)

    # Configure the main application logger
    handler = logging.StreamHandler(sys.stderr)

    if env in ["production", "beta"]:
        handler.setFormatter(StructuredFormatter())
    else:
        # Clearer format for local development
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
        handler.setFormatter(formatter)

    # Remove existing handlers from app.logger
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(log_level)

    # Ensure other loggers (like gunicorn) use our handler if needed
    # but for now, we focus on the app logger.

    app._logging_setup_done = True  # type: ignore[attr-defined]
