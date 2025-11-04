"""Decorators for the auth blueprint."""

from functools import wraps

from flask import flash, redirect, session, url_for


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

    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
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
