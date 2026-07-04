"""Decorators for the auth blueprint."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Response, flash, g, redirect, session, url_for

from pickaladder.constants.messages import AUTH_MESSAGES


# TODO: Add type hints for Agent clarity
def login_required(
    f: Callable[..., Any] | None = None,
    admin_required: bool = False,
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
        def decorated_function(*args: object, **kwargs: object) -> Response:
            """Ensure user is logged in before accessing the view."""
            if not g.get("user"):
                return redirect(url_for("auth.login"))  # type: ignore
            if admin_required and not session.get("is_admin"):
                flash(AUTH_MESSAGES["UNAUTHORIZED"], "danger")
                return redirect(url_for("user.dashboard"))  # type: ignore
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
    def decorated_function(*args: object, **kwargs: object) -> Response:
        if not g.get("user"):
            return redirect(url_for("auth.login"))  # type: ignore
        if not session.get("is_admin"):
            flash(AUTH_MESSAGES["ADMIN_ONLY_TOURNAMENT"], "danger")
            return redirect(url_for("user.dashboard"))  # type: ignore
        return f(*args, **kwargs)

    return decorated_function
