from functools import wraps
from flask import flash, redirect, url_for, session


def login_required(f=None, admin_required=False):
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login"))
            if admin_required and not session.get("is_admin"):
                flash("You are not authorized to view this page.", "danger")
                return redirect(url_for("user.dashboard"))
            return func(*args, **kwargs)

        return decorated_function

    if f:
        return decorator(f)
    return decorator
