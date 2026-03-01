"""Admin routes for the application."""

import datetime
import random
from typing import Any, Union

from faker import Faker
from firebase_admin import auth, firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import (
    ADMIN_MESSAGES,
    AUTH_MESSAGES,
    COMMON_MESSAGES,
)
from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService
from pickaladder.user import UserService
from pickaladder.user.models import UserSession

from . import bp
from .services import AdminService

MIN_USERS_FOR_MATCH_GENERATION = 2


@bp.route("/")
@login_required(admin_required=True)
def admin() -> Union[str, Response]:
    """Render the main admin dashboard."""
    if not g.user or (not g.user.get("isAdmin") and not g.get("is_impersonating")):
        flash(AUTH_MESSAGES["UNAUTHORIZED"], "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()
    admin_stats = AdminService.get_admin_stats(db)
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    email_verification_setting = setting_ref.get()
    users = UserService.get_all_users(db, limit=50, public_only=False)

    return render_template(
        "admin/admin.html",
        admin_stats=admin_stats,
        users=users,
        email_verification_setting=email_verification_setting.to_dict()
        if email_verification_setting.exists
        else {"value": False},
    )


@bp.route("/merge-ghost", methods=["POST"])
@login_required(admin_required=True)
def merge_ghost() -> Response:
    """Merge a ghost account into a real user profile."""
    target_user_id = request.form.get("target_user_id")
    ghost_email = request.form.get("ghost_email")

    if not target_user_id or not ghost_email:
        flash(ADMIN_MESSAGES["MERGE_REQUIRED_FIELDS"], "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    real_user_ref = db.collection("users").document(target_user_id)
    try:
        if UserService.merge_ghost_user(db, real_user_ref, ghost_email):
            flash(ADMIN_MESSAGES["GHOST_MERGE_SUCCESS"], "success")
        else:
            flash(ADMIN_MESSAGES["GHOST_MERGE_FAILED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")

    return redirect(url_for(".admin"))


@bp.route("/announcement", methods=["POST"])
@login_required(admin_required=True)
def announcement() -> Response:
    """Update the global system announcement."""
    db = firestore.client()
    try:
        db.collection("system").document("settings").set(
            {
                "announcement_text": request.form.get("announcement_text"),
                "is_active": request.form.get("is_active") == "on",
                "level": request.form.get("level", "info"),
            },
            merge=True,
        )
        flash(ADMIN_MESSAGES["ANNOUNCEMENT_UPDATED"], "success")
    except Exception as e:
        flash(ADMIN_MESSAGES["ANNOUNCEMENT_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/toggle_email_verification", methods=["POST"])
@login_required(admin_required=True)
def toggle_email_verification() -> Response:
    """Toggle the global setting for requiring email verification."""
    db = firestore.client()
    try:
        new_val = AdminService.toggle_setting(db, "enforceEmailVerification")
        status = "enabled" if new_val else "disabled"
        flash(
            ADMIN_MESSAGES["EMAIL_VERIFY_TOGGLED"].format(status=status),
            "success",
        )
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/matches")
@login_required(admin_required=True)
def admin_matches() -> str:
    """Display a list of all matches."""
    db = firestore.client()
    try:
        matches = (
            db.collection("matches")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
    except KeyError:
        matches = db.collection("matches").limit(50).stream()
    return render_template("admin/matches.html", matches=matches)


@bp.route("/delete_match/<string:match_id>", methods=["POST"])
@login_required(admin_required=True)
def admin_delete_match(match_id: str) -> Response:
    """Delete a match document from Firestore."""
    db = firestore.client()
    try:
        db.collection("matches").document(match_id).delete()
        flash(ADMIN_MESSAGES["MATCH_DELETE_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin_matches"))


@bp.route("/friend_graph_data")
@login_required(admin_required=True)
def friend_graph_data() -> Union[Response, tuple[Response, int]]:
    """Provide data for a network graph of users and their friendships."""
    try:
        return jsonify(AdminService.build_friend_graph(firestore.client()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _lookup_user_by_identifier(
    db: Any, identifier: str
) -> tuple[str | None, str | None]:
    """Look up a user UID and email by their identifier (ID or Email)."""
    user_doc = db.collection("users").document(identifier).get()
    if user_doc.exists:
        return user_doc.id, user_doc.to_dict().get("email")

    users = list(
        db.collection("users")
        .where(filter=firestore.FieldFilter("email", "==", identifier))
        .limit(1)
        .stream()
    )
    if users:
        return users[0].id, users[0].to_dict().get("email")
    return None, None


def _perform_user_deletion(db: Any, uid: str, email: str | None) -> None:
    """Orchestrate the deletion of a user and flash results."""
    try:
        AdminService.delete_user(db, uid)
        flash(
            ADMIN_MESSAGES["USER_DELETED_COUNT"].format(identifier=email or uid),
            "success",
        )
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")


@bp.route("/delete_user", methods=["POST"])
@login_required(admin_required=True)
def admin_delete_user() -> Response:
    """Delete a user by ID or Email."""
    user_identifier = request.form.get("user_identifier")
    if not user_identifier:
        flash(ADMIN_MESSAGES["USER_ID_EMAIL_REQUIRED"], "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    uid, email = _lookup_user_by_identifier(db, user_identifier)
    if uid:
        _perform_user_deletion(db, uid, email)
    else:
        flash(
            ADMIN_MESSAGES["USER_NOT_FOUND"].format(identifier=user_identifier),
            "danger",
        )
    return redirect(url_for(".admin"))


@bp.route("/delete_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def delete_user(user_id: str) -> Response:
    """Delete a user from Firebase Auth and Firestore."""
    try:
        AdminService.delete_user(firestore.client(), user_id)
        flash(ADMIN_MESSAGES["USER_DELETE_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/promote_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def promote_user(user_id: str) -> Response:
    """Promote a user to admin status in Firestore."""
    try:
        name = AdminService.promote_user(firestore.client(), user_id)
        flash(ADMIN_MESSAGES["ADMIN_PROMOTION"].format(name=name), "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/verify_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def verify_user(user_id: str) -> Response:
    """Manually verify a user's email."""
    try:
        AdminService.verify_user(firestore.client(), user_id)
        flash(ADMIN_MESSAGES["EMAIL_VERIFIED_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/generate_users", methods=["POST"])
def generate_users() -> str:
    """Generate fake users for testing."""
    db, fake, new_users = firestore.client(), Faker(), []
    try:
        for _ in range(10):
            email, password = (
                fake.email(),
                fake.password(
                    length=12,
                    special_chars=True,
                    digits=True,
                    upper_case=True,
                    lower_case=True,
                ),
            )
            user_record = auth.create_user(email=email, password=password)
            user_doc = {
                "username": fake.user_name(),
                "email": email,
                "name": fake.name(),
                "duprRating": round(random.uniform(2.5, 7.0), 2),  # nosec B311
                "isAdmin": False,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            db.collection("users").document(user_record.uid).set(user_doc)
            new_users.append({"uid": user_record.uid, **user_doc})
        flash(
            ADMIN_MESSAGES["USERS_GEN_SUCCESS"].format(count=len(new_users)), "success"
        )
    except Exception as e:
        flash(ADMIN_MESSAGES["USERS_GEN_ERROR"].format(error=e), "danger")
    return render_template("generated_users.html", users=new_users)


def _generate_single_random_match(db: Any, users: list[Any]) -> bool:
    """Generate a single random match between users."""
    p1, p2 = random.sample(users, 2)  # nosec B311
    s1, s2 = 11, random.randint(0, 9)  # nosec B311
    if random.choice([True, False]):  # nosec B311
        s1, s2 = s2, s1

    submission = MatchSubmission(
        player_1_id=p1.id,
        player_2_id=p2.id,
        score_p1=s1,
        score_p2=s2,
        match_type="singles",
        match_date=datetime.datetime.now(datetime.timezone.utc),
        created_by=p1.id,
    )
    try:
        MatchService.record_match(db, submission, UserSession({"uid": p1.id}))
        return True
    except Exception:
        return False


def _batch_generate_random_matches(db: Any, users: list[Any], count: int = 10) -> int:
    """Generate multiple random matches and return success count."""
    return sum(1 for _ in range(count) if _generate_single_random_match(db, users))


@bp.route("/generate_matches", methods=["POST"])
@login_required(admin_required=True)
def generate_matches() -> Response:
    """Generate random matches between existing users."""
    db = firestore.client()
    try:
        users = list(db.collection("users").limit(20).stream())
        if len(users) < MIN_USERS_FOR_MATCH_GENERATION:
            flash(ADMIN_MESSAGES["NOT_ENOUGH_USERS_MATCHES"], "warning")
        else:
            count = _batch_generate_random_matches(db, users)
            flash(ADMIN_MESSAGES["RANDOM_MATCHES_GEN"].format(count=count), "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin"))


@bp.route("/merge_players", methods=["GET", "POST"])
@login_required(admin_required=True)
def merge_players() -> Union[str, Response]:
    """Merge two player accounts (Source -> Target)."""
    db = firestore.client()
    if request.method == "POST":
        sid, tid = request.form.get("source_id"), request.form.get("target_id")
        if not sid or not tid or sid == tid:
            flash(ADMIN_MESSAGES["INVALID_MERGE_IDS"], "error")
        else:
            try:
                UserService.merge_users(db, sid, tid)
                flash(ADMIN_MESSAGES["PLAYERS_MERGE_SUCCESS"], "success")
            except Exception as e:
                flash(ADMIN_MESSAGES["PLAYERS_MERGE_ERROR"].format(error=e), "error")
        return redirect(url_for(".merge_players"))

    users = sorted(
        UserService.get_all_users(db, public_only=False),
        key=lambda u: (u.get("is_ghost", False), u.get("name", "").lower()),
    )
    return render_template("admin/merge_players.html", users=users)


@bp.route("/style-guide")
@login_required(admin_required=True)
def style_guide() -> str:
    """Render the design system style guide."""
    # Mock data for Tournament Card
    mock_tournament = {
        "id": "mock-t-1",
        "name": "The Volt Championship",
        "matchType": "doubles",
        "status": "PUBLISHED",
        "date": "2024-12-01",
        "date_display": "Dec 1, 2024",
        "location": "Central Courts",
        "organizer_id": "admin-1",
        "banner_url": None,
    }

    # Mock data for Match Row
    mock_match = {
        "id": "mock-m-1",
        "date": datetime.datetime.now(),
        "match_type": "singles",
        "player_1_data": {"uid": "user-1", "display_name": "Jules"},
        "player_2_data": {"uid": "user-2", "display_name": "Opponent"},
        "player1_score": 11,
        "player2_score": 8,
        "user_result": "win",
        "tournament_name": "The Volt Championship",
        "created_by": "user-1",
    }

    return render_template(
        "admin/style_guide.html",
        tournament=mock_tournament,
        match=mock_match,
    )


@bp.route("/styleguide")
@login_required(admin_required=True)
def styleguide() -> str:
    """Render the legacy design system styleguide."""
    return render_template("admin/styleguide.html")


@bp.route("/impersonate/<string:user_id>")
@login_required(admin_required=True)
def impersonate(user_id: str) -> Response:
    """Start impersonating another user."""
    session["impersonate_id"] = user_id
    doc = firestore.client().collection("users").document(user_id).get()
    name = doc.to_dict().get("name", "User") if doc.exists else "User"
    flash(ADMIN_MESSAGES["IMPERSONATION_START"].format(name=name), "success")
    return redirect(url_for("user.dashboard"))


@bp.route("/stop_impersonating")
@login_required
def stop_impersonating() -> Response:
    """Stop impersonating and return to admin profile."""
    session.pop("impersonate_id", None)
    flash(ADMIN_MESSAGES["ADMIN_WELCOME"], "success")
    return redirect(url_for("admin.admin"))
