from functools import wraps
from flask import request, g, current_app, redirect, url_for, flash
from firebase_admin import auth, firestore

def login_required(f=None, admin_required=False):
    def decorator(func):
        @wraps(func)
        def decorated_function(*args, **kwargs):
            if current_app.config.get("LOGIN_DISABLED"):
                g.user = {"uid": "test_user_id", "isAdmin": admin_required}
                return func(*args, **kwargs)

            id_token = request.headers.get("Authorization", "").split("Bearer ")[-1]
            if not id_token:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login"))

            try:
                decoded_token = auth.verify_id_token(id_token)
                g.user = decoded_token
                db = firestore.client()
                user_doc = db.collection("users").document(g.user["uid"]).get()
                if user_doc.exists:
                    g.user.update(user_doc.to_dict())
                else:
                    # This can happen if a user is deleted from Firestore but not Auth.
                    current_app.logger.warning(
                        f"User {g.user['uid']} exists in Auth but not in Firestore."
                    )
                    flash("User not found.", "danger")
                    return redirect(url_for("auth.login"))

                if admin_required and not g.user.get("isAdmin"):
                    flash("You are not authorized to view this page.", "danger")
                    return redirect(url_for("auth.login"))
                elif admin_required and g.user.get("isAdmin"):
                    return f(*args, **kwargs)
            except auth.InvalidIdTokenError:
                flash("Invalid or expired session. Please log in again.", "danger")
                return redirect(url_for("auth.login"))
            except Exception as e:
                current_app.logger.error(f"Unexpected error during authentication: {e}")
                flash("An unexpected error occurred. Please try again.", "danger")
                return redirect(url_for("auth.login"))

            return func(*args, **kwargs)
        return decorated_function

    if f:
        return decorator(f)
    return decorator