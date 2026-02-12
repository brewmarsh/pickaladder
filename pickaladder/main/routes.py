"""Routes for the main blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app, send_from_directory

from . import bp

if TYPE_CHECKING:
    from flask import Response


@bp.route("/service-worker.js")
def service_worker() -> Response:
    """Serve the service worker file."""
    static_folder = current_app.static_folder
    if static_folder is None:
        raise RuntimeError("Static folder is not configured.")
    return send_from_directory(static_folder, "service-worker.js")
