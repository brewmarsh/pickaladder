import os
import json
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    g,
    jsonify,
    Response,
)
from firebase_admin import auth, firestore
from werkzeug.exceptions import UnprocessableEntity

from . import bp
from .forms import LoginForm, RegisterForm
from pickaladder.errors import DuplicateResourceError
from pickaladder.utils import send_email


@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        db = firestore.client()
        username = form.username.data
        email = form.email.data
        password = form.password.data

        # Check if username is already taken in Firestore
        users_ref = db.collection("users")
        if users_ref.where("username", "==", username).limit(1).get():
            flash("Username already exists. Please choose a different one.", "danger")
            return redirect(url_for(".register"))

        try:
            # Create user in Firebase Authentication
            user_record = auth.create_user(
                email=email, password=password, email_verified=False
            )

            # Send email verification
            verification_link = auth.generate_email_verification_link(email)
            send_email(
                to=email,
                subject="Verify Your Email",
                template="email/verify_email.html",
                user={"username": username},
                verification_link=verification_link,
            )

            # Create user document in Firestore
            user_doc_ref = db.collection("users").document(user_record.uid)
            user_doc_ref.set(
                {
                    "username": username,
                    "email": email,
                    "name": form.name.data,
                    "duprRating": float(form.dupr_rating.data),
                    "isAdmin": False,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
            )

            flash(
                "Registration successful! Please check your email to verify your account.",
                "success",
            )
            # Client-side will handle login and redirect to dashboard
            return redirect(url_for(".login"))

        except auth.EmailAlreadyExistsError:
            flash("Email address is already registered.", "danger")
        except Exception as e:
            current_app.logger.error(f"Error during registration: {e}")
            flash("An unexpected error occurred during registration.", "danger")

        return redirect(url_for(".register"))

    return render_template("register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Renders the login page.
    The actual login process is handled by the Firebase client-side SDK.
    The client will get an ID token and send it with subsequent requests.
    """
    current_app.logger.info("Login page loaded")
    db = firestore.client()
    # Check if an admin user exists to determine if we should run install
    admin_query = db.collection("users").where("isAdmin", "==", True).limit(1).get()
    if not admin_query:
        return redirect(url_for("auth.install"))

    form = LoginForm()
    # The form is now just for presentation, validation is on the client
    return render_template("login.html", form=form)


@bp.route("/session_login", methods=["POST"])
def session_login():
    """
    This endpoint is called from the client-side after a successful Firebase login.
    It receives the ID token, verifies it, and creates a server-side session.
    """
    id_token = request.json.get("idToken")
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        db = firestore.client()
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            user_info = user_doc.to_dict()
            session["user_id"] = uid
            session["is_admin"] = user_info.get("isAdmin", False)
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "error", "message": "User not found in Firestore."}), 404
    except Exception as e:
        current_app.logger.error(f"Error during session login: {e}")
        return jsonify({"status": "error", "message": "Invalid token or server error."}), 401


@bp.route("/logout")
def logout():
    """
    The actual logout is handled by the Firebase client-side SDK.
    This route is for clearing any server-side session info if needed.
    """
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@bp.route("/install", methods=["GET", "POST"])
def install():
    db = firestore.client()
    # Check if an admin user already exists
    admin_query = db.collection("users").where("isAdmin", "==", True).limit(1).get()
    if admin_query:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")

        if not all([email, password, username]):
            flash("Missing required fields for admin creation.", "danger")
            return redirect(url_for(".install"))

        try:
            # Create user in Firebase Auth
            admin_user_record = auth.create_user(
                email=email, password=password, email_verified=True
            )

            # Create admin user document in Firestore
            admin_doc_ref = db.collection("users").document(admin_user_record.uid)
            admin_doc_ref.set(
                {
                    "username": username,
                    "email": email,
                    "name": request.form.get("name", ""),
                    "duprRating": float(request.form.get("dupr_rating") or 0),
                    "isAdmin": True,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
            )

            # Also create the email verification setting
            settings_ref = db.collection("settings").document(
                "enforceEmailVerification"
            )
            settings_ref.set({"value": True})

            flash("Admin user created successfully. You can now log in.", "success")
            return redirect(url_for("auth.login"))

        except auth.EmailAlreadyExistsError:
            # This could happen in a race condition. We'll try to find the
            # user and grant them admin rights if they are not already an admin.
            try:
                user = auth.get_user_by_email(email)
                user_doc_ref = db.collection("users").document(user.uid)
                user_doc = user_doc_ref.get()
                if user_doc.exists and not user_doc.to_dict().get("isAdmin"):
                    user_doc_ref.update({"isAdmin": True})
                    flash("An existing user was promoted to admin.", "info")
                    return redirect(url_for("auth.login"))
                else:
                    raise DuplicateResourceError(
                        "An admin user with this email already exists."
                    )
            except auth.UserNotFoundError:
                raise UnprocessableEntity("Could not create or find user.")

        except Exception as e:
            current_app.logger.error(f"Error during installation: {e}")
            flash("An unexpected error occurred during installation.", "danger")

    return render_template("install.html")


@bp.route("/change_password", methods=["GET"])
def change_password():
    """
    Renders the change password page.
    The actual password change is handled by the Firebase client-side SDK.
    """
    if not g.get("user"):
        return redirect(url_for("auth.login"))
    return render_template("change_password.html", user=g.user)


@bp.route('/firebase-config.js')
def firebase_config():
    api_key = os.environ.get("FIREBASE_API_KEY")
    if not api_key:
        current_app.logger.error("FIREBASE_API_KEY is not set. Frontend will not be able to connect to Firebase.")
        error_script = 'console.error("Firebase API key is missing. Please set the FIREBASE_API_KEY environment variable.");'
        return Response(error_script, mimetype='application/javascript')

    config = {
        "apiKey": api_key,
        "authDomain": "pickaladder.firebaseapp.com",
        "projectId": "pickaladder",
        "storageBucket": "pickaladder.appspot.com",
        "messagingSenderId": "402457219675",
        "appId": "1:402457219675:web:a346e2dc0dfa732d31e57e",
        "measurementId": "G-E28CXCXTSK"
    }
    js_config = f"const firebaseConfig = {json.dumps(config)};"
    return Response(js_config, mimetype='application/javascript')
    config = f"""
const firebaseConfig = {{
  apiKey: "{api_key}",
    config = f"""
const firebaseConfig = {{
  apiKey: "{os.environ.get("FIREBASE_API_KEY")}",
  authDomain: "pickaladder.firebaseapp.com",
  projectId: "pickaladder",
  storageBucket: "pickaladder.appspot.com",
  messagingSenderId: "402457219675",
  appId: "1:402457219675:web:a346e2dc0dfa732d31e57e",
  measurementId: "G-E28CXCXTSK"
}};
"""
    return Response(config, mimetype='application/javascript')
