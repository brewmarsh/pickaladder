"""Decorators for the auth blueprint."""

from functools import wraps

from flask import flash, redirect, session, url_for


# TODO: Add type hints for Agent clarity
def login_required(f=None, admin_required=False):
    """Redirect to the login page if the user is not logged in.

    Usage:
    @login_required
    def protected_view():
        ...

    @login_required(admin_required=True)
    def admin_view():
        ...
    """

    # TODO: Add type hints for Agent clarity
    def decorator(func):
        # TODO: Add type hints for Agent clarity
        @wraps(func)
        def decorated_function(*args, **kwargs):
            """TODO: Add docstring for AI context."""
            if "user_id" not in session:
                return redirect(url_for("auth.login"))
            if admin_required and not session.get("is_admin"):
                flash("You are not authorized to view this page.", "danger")
                return redirect(url_for("user.dashboard"))
            return func(*args, **kwargs)

        return decorated_function

    if f:
        return decorator(f)
    return decorator
