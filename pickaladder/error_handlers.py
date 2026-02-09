"""Error handlers for the application."""

from typing import Tuple, Union  # noqa: UP035

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_wtf.csrf import CSRFError
from werkzeug.wrappers import Response

from .errors import AppError, DuplicateResourceError, NotFoundError, ValidationError

error_handlers_bp = Blueprint("error_handlers", __name__)


@error_handlers_bp.app_errorhandler(ValidationError)
def handle_validation_error(error: ValidationError) -> Tuple[str, int]:  # noqa: UP006
    """Handle validation errors by rendering a generic error page."""
    current_app.logger.warning(f"Validation Error: {error.message}")
    return render_template("error.html", error=error.message), error.status_code


@error_handlers_bp.app_errorhandler(DuplicateResourceError)
def handle_duplicate_resource_error(error: DuplicateResourceError) -> Tuple[str, int]:  # noqa: UP006
    """Handle duplicate resource errors."""
    current_app.logger.warning(f"Duplicate Resource Error: {error.message}")
    return render_template("error.html", error=error.message), error.status_code


@error_handlers_bp.app_errorhandler(NotFoundError)
def handle_not_found_error(error: NotFoundError) -> Tuple[str, int]:  # noqa: UP006
    """Handle not found errors."""
    current_app.logger.warning(f"Not Found Error: {error.message}")
    return render_template("404.html", error=error.message), error.status_code


@error_handlers_bp.app_errorhandler(AppError)
def handle_app_error(error: AppError) -> Tuple[str, int]:  # noqa: UP006
    """Handle generic application errors."""
    current_app.logger.error(f"Application Error: {error.message}")
    return render_template("error.html", error=error.message), error.status_code


@error_handlers_bp.app_errorhandler(404)
def handle_404(e: Exception) -> Tuple[str, int]:  # noqa: UP006
    """Handle generic 404 errors for routes that don't exist."""
    return render_template("404.html"), 404


@error_handlers_bp.app_errorhandler(500)
def handle_500(e: Exception) -> Tuple[str, int]:  # noqa: UP006
    """Handle unexpected server errors."""
    current_app.logger.error(f"Internal Server Error: {e}")
    return render_template("500.html"), 500


@error_handlers_bp.app_errorhandler(CSRFError)
def handle_csrf_error(e: CSRFError) -> Union[Response, str]:
    """Handle CSRF errors.

    Handle CSRF errors, which usually indicate a session timeout or invalid form
    submission.
    """
    current_app.logger.warning(f"CSRF Error: {e.description}")
    flash("Your session has expired. Please try again.", "info")
    return redirect(url_for("auth.login"))
