"""Routes for the main blueprint."""

from flask import Response, current_app, send_from_directory

from . import bp


@bp.route("/service-worker.js")
def service_worker() -> Response:
    """Serve the service worker file."""
    return send_from_directory(current_app.static_folder, "service-worker.js")
