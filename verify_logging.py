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
                "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
            )
            handler.setFormatter(formatter)
        app.logger.addHandler(handler)

        app.logger.info("Test message")
    finally:
        sys.stderr = old_stderr

    return output_capture.getvalue().strip()


print("--- Development ---")
dev_output = test_logging("development")
print(f"DEBUG dev_output: '{dev_output}'")

print("--- Production ---")
prod_output = test_logging("production")
print(f"DEBUG prod_output: '{prod_output}'")

# Basic verification
if "Test message" in dev_output and "INFO" in dev_output:
    print("Dev logging: OK")
else:
    print("Dev logging: FAILED")

try:
    data = json.loads(prod_output)
    if data["message"] == "Test message" and data["level"] == "INFO":
        print("Prod logging: OK (JSON valid)")
    else:
        print("Prod logging: FAILED (JSON invalid or missing data)")
except Exception as e:
    print(f"Prod logging: FAILED (Exception: {e})")
