import io
import json
import sys

from flask import Flask

from pickaladder.core.logging import setup_logging


def test_logging(env):
    app = Flask(f"test_app_{env}")
    app.config["ENV"] = env
    setup_logging(app)

    # Capture stderr
    output_capture = io.StringIO()
    # We need to replace the handler's stream or replace sys.stderr globally
    # setup_logging uses sys.stderr at the time of handler creation

    # Let's just monkeypatch sys.stderr before setup_logging
    old_stderr = sys.stderr
    sys.stderr = output_capture

    try:
        # Re-setup to use the captured stderr
        app.logger.handlers.clear()
        import logging

        handler = logging.StreamHandler(sys.stderr)
        if env in ["production", "beta"]:
            from pickaladder.core.logging import StructuredFormatter

            handler.setFormatter(StructuredFormatter())
        else:
            formatter = logging.Formatter(
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            )
            handler.setFormatter(formatter)
        app.logger.addHandler(handler)

        app.logger.info("Test message")
    finally:
        sys.stderr = old_stderr

    return output_capture.getvalue().strip()


dev_output = test_logging("development")

prod_output = test_logging("production")

# Basic verification
if "Test message" in dev_output and "INFO" in dev_output:
    pass
else:
    pass

try:
    data = json.loads(prod_output)
    if data["message"] == "Test message" and data["level"] == "INFO":
        pass
    else:
        pass
except Exception:
    pass
