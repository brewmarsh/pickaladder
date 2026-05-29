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
        msg = "Static folder is not configured."
        raise RuntimeError(msg)
    return send_from_directory(static_folder, "service-worker.js")


@bp.route("/offline")
def offline() -> str:
    """Render the offline fallback page."""
    from flask import render_template

    return render_template("offline.html")


@bp.route("/robots.txt")
def robots() -> Response:
    """Serve the robots.txt file."""
    static_folder = current_app.static_folder
    if static_folder is None:
        msg = "Static folder is not configured."
        raise RuntimeError(msg)
    return send_from_directory(static_folder, "robots.txt")


@bp.route("/sitemap.xml")
def sitemap() -> Response:
    """Generate and serve sitemap.xml."""
    from flask import make_response, url_for

    pages = []
    # Static pages
    for rule in current_app.url_map.iter_rules():
        if "GET" in rule.methods and len(rule.arguments) == 0:
            # Skip private/admin routes
            if any(
                x in rule.rule
                for x in [
                    "/admin",
                    "/settings",
                    "/logout",
                    "/api",
                    "/impersonate",
                    "/health",
                    "/service-worker.js",
                    "/offline",
                ]
            ):
                continue
            pages.append(url_for(rule.endpoint, _external=True))

    # Add specific public routes if not caught
    public_routes = [
        url_for("main.index", _external=True)
        if "main.index" in current_app.view_functions
        else None,
        url_for("auth.login", _external=True),
        url_for("auth.register", _external=True),
        url_for("match.leaderboard", _external=True),
    ]
    for r in public_routes:
        if r and r not in pages:
            pages.append(r)

    sitemap_xml = render_template("sitemap.xml", pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response


@bp.route("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
