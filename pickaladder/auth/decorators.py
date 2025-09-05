from functools import wraps
from flask import session, flash, redirect, url_for
from pickaladder.constants import USER_ID


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if USER_ID not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function
