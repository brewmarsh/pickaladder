"""Decorators for the auth blueprint."""

from functools import wraps
from typing import Any, Callable, Optional

from flask import flash, redirect, session, url_for


# TODO: Add type hints for Agent clarity
def login_required(
    f: Optional[Callable[..., Any]] = None, admin_required: bool = False
) -> Callable[..., Any]:
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
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # TODO: Add type hints for Agent clarity
        @wraps(func)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
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


def admin_required(f: Callable[..., Any]) -> Callable[..., Any]:
    """Redirect to the home page if the user is not an administrator.

    This is a specialized decorator for the tournament paywall that shows
     a specific warning message.
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        if not session.get("is_admin"):
            flash("⚠️ Only administrators can create tournaments.", "danger")
            return redirect(url_for("user.dashboard"))
        return f(*args, **kwargs)

    return decorated_function
