from flask import Blueprint, render_template, current_app
import psycopg2
from .errors import AppError, ValidationError, DuplicateResourceError, NotFoundError

error_handlers_bp = Blueprint('error_handlers', __name__)

@error_handlers_bp.app_errorhandler(ValidationError)
def handle_validation_error(error):
    """Handles validation errors by rendering a generic error page."""
    current_app.logger.warning(f"Validation Error: {error.message}")
    return render_template('error.html', error=error.message), error.status_code

@error_handlers_bp.app_errorhandler(DuplicateResourceError)
def handle_duplicate_resource_error(error):
    """Handles duplicate resource errors."""
    current_app.logger.warning(f"Duplicate Resource Error: {error.message}")
    return render_template('error.html', error=error.message), error.status_code

@error_handlers_bp.app_errorhandler(NotFoundError)
def handle_not_found_error(error):
    """Handles not found errors."""
    current_app.logger.warning(f"Not Found Error: {error.message}")
    return render_template('404.html', error=error.message), error.status_code

@error_handlers_bp.app_errorhandler(AppError)
def handle_app_error(error):
    """Handles generic application errors."""
    current_app.logger.error(f"Application Error: {error.message}")
    return render_template('error.html', error=error.message), error.status_code

@error_handlers_bp.app_errorhandler(404)
def handle_404(e):
    """Handles generic 404 errors for routes that don't exist."""
    return render_template('404.html'), 404

@error_handlers_bp.app_errorhandler(500)
def handle_500(e):
    """Handles unexpected server errors."""
    current_app.logger.error(f"Internal Server Error: {e}")
    return render_template('500.html'), 500

@error_handlers_bp.app_errorhandler(psycopg2.Error)
def handle_db_error(e):
    """Handles database errors."""
    current_app.logger.error(f"Database Error: {e}")
    # Avoid exposing raw database error details to the user
    return render_template('error.html', error="A database error occurred. Please try again later."), 500
