from functools import wraps
from flask import session, flash, redirect, url_for
from pickaladder.constants import USER_IS_ADMIN

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get(USER_IS_ADMIN):
            flash("You are not authorized to view this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function
