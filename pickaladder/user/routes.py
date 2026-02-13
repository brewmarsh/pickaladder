"""Routes for the user blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.core.constants import DUPR_PROFILE_BASE_URL

from . import bp
from .forms import SettingsForm, UpdateUserForm
from .services import UserService

if TYPE_CHECKING:
    pass


class MockPagination:
    """A mock pagination object."""

    def __init__(self, items: list[Any]) -> None:
        """Initialize the mock pagination object."""
        self.items = items
        self.pages = 1


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings() -> Any:
    """Unified user settings page."""
    db = firestore.client()
    user_id = g.user["uid"]
    form = SettingsForm()

    if request.method == "GET":
        form.name.data = g.user.get("name")
        form.username.data = g.user.get("username")
        form.email.data = g.user.get("email")
        form.dupr_id.data = g.user.get("dupr_id")
        # Explicitly map data to form fields to ensure compatibility
        form.dupr_rating.data = g.user.get("duprRating") or g.user.get("dupr_rating")
        form.dark_mode.data = g.user.get("dark_mode")

    if form.validate_on_submit():
        # Handle profile picture upload
        profile_pic_url = None
        if form.profile_picture.data:
            profile_pic_url = UserService.upload_profile_picture(
                user_id, form.profile_picture.data
            )

        # Update base fields (dark_mode and profile_pic if uploaded)
        update_data: dict[str, Any] = {"dark_mode": bool(form.dark_mode.data)}
        if profile_pic_url:
            update_data["profilePictureUrl"] = profile_pic_url

        UserService.update_user_profile(db, user_id, update_data)

        # Handle other updates (name, username, email, dupr)
        res = UserService.process_profile_update(db, user_id, form, g.user)

        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash("Settings updated successfully.", "success")
            return redirect(url_for(".settings"))
        flash(res["error"], "danger")

    return render_template("user/settings.html", form=form, user=g.user)


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile() -> Any:
    """Handle user profile updates."""
    form = UpdateUserForm(data=g.user)
    if form.validate_on_submit():
        res = UserService.process_profile_update(
            firestore.client(), g.user["uid"], form, g.user
        )
        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash("Account updated successfully.", "success")
            return redirect(url_for(".edit_profile"))
        flash(res["error"], "danger")
    return render_template("user/edit_profile.html", form=form, user=g.user)


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard() -> Any:
    """Render user dashboard."""
    db = firestore.client()
    user_id = g.user["uid"]

    data = UserService.get_dashboard_data(db, user_id)

    # Calculate engagement features
    processed_matches = data.get("stats", {}).get("processed_matches", [])
    all_match_docs = [m["doc"] for m in processed_matches]
    current_streak = UserService.calculate_current_streak(user_id, all_match_docs)
    recent_opponents = UserService.get_recent_opponents(db, user_id, all_match_docs)

    # Onboarding / Rookie Flow logic
    user_friends_count = len(data.get("friends", []))
    user_groups = data.get("group_rankings", [])
    total_matches = data.get("stats", {}).get("total_games", 0)

    onboarding_status = {
        "has_avatar": g.user.get("avatar_url") != "default",
        "has_rating": (g.user.get("dupr_rating") or 0) > 0,
        "has_friend": user_friends_count > 0,
        "has_group": len(user_groups) > 0,
        "has_match": total_matches > 0,
    }
    is_active = total_matches > 0

    return render_template(
        "user_dashboard.html",
        current_streak=current_streak,
        recent_opponents=recent_opponents,
        onboarding_status=onboarding_status,
        is_active=is_active,
        **data,
    )


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id: str) -> Any:
    """Display a user's public profile."""
    db = firestore.client()
    data = UserService.get_user_profile_data(db, g.user["uid"], user_id)
    if not data:
        flash("User not found.", "danger")
        return redirect(url_for(".users"))
    return render_template(
        "user/profile.html",
        user=g.user,
        dupr_url_base=DUPR_PROFILE_BASE_URL,
        record={"wins": data["stats"]["wins"], "losses": data["stats"]["losses"]},
        total_games=data["stats"]["total_games"],
        win_rate=data["stats"]["win_rate"],
        current_streak=data["stats"]["current_streak"],
        streak_type=data["stats"]["streak_type"],
        **data,
    )


@bp.route("/community")
@login_required
def view_community() -> Any:
    """Render the community hub."""
    db = firestore.client()
    search_term = request.args.get("search", "").strip()

    incoming_requests = UserService.get_user_pending_requests(db, user_id=g.user["uid"])
    outgoing_requests = UserService.get_user_sent_requests(db, user_id=g.user["uid"])

    data = UserService.get_community_data(db, g.user["uid"], search_term)

    # Filter out incoming/outgoing requests from data to avoid multiple values error
    filtered_data = {
        k: v
        for k, v in data.items()
        if k not in ["incoming_requests", "outgoing_requests"]
    }

    return render_template(
        "community.html",
        search_term=search_term,
        user=g.user,
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
        **filtered_data,
    )


@bp.route("/users")
@login_required
def users() -> Any:
    """List and allows searching for users."""
    search_term = request.args.get("search", "")
    user_items = UserService.search_users(
        firestore.client(), g.user["uid"], search_term
    )
    return render_template(
        "users.html",
        pagination=MockPagination(user_items),
        search_term=search_term,
        fof=[],
    )


@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id: str) -> Any:
    """Send a friend request."""
    if g.user["uid"] == friend_id:
        flash("You cannot send a friend request to yourself.", "danger")
        return redirect(url_for(".users"))

    success = UserService.send_friend_request(
        firestore.client(), g.user["uid"], friend_id
    )
    if success:
        flash("Friend request sent.", "success")
    else:
        flash("An error occurred while sending the friend request.", "danger")

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"success": success})
    return redirect(url_for(".users"))


@bp.route("/friends")
@login_required
def friends() -> Any:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))


@bp.route("/requests", methods=["GET"])
@login_required
def friend_requests() -> Any:
    """Deprecated: Redirects to the community hub."""
    return redirect(url_for(".view_community"))


@bp.route("/requests/<string:requester_id>/accept", methods=["POST"])
@bp.route("/accept_friend_request/<string:requester_id>", methods=["POST"])
@login_required
def accept_request(requester_id: str) -> Any:
    """Accept a friend request."""
    db = firestore.client()
    requester = UserService.get_user_by_id(db, requester_id)
    name = UserService.smart_display_name(requester) if requester else "the user"

    if UserService.accept_friend_request(db, g.user["uid"], requester_id):
        flash(f"You are now friends with {name}!", "success")
    else:
        flash("An error occurred.", "danger")

    return redirect(request.referrer or url_for(".view_community"))


@bp.route("/requests/<string:target_id>/cancel", methods=["POST"])
@bp.route("/decline_friend_request/<string:target_id>", methods=["POST"])
@login_required
def cancel_request(target_id: str) -> Any:
    """Cancel or decline a friend request."""
    if UserService.cancel_friend_request(firestore.client(), g.user["uid"], target_id):
        flash("Friend request processed.", "success")
    else:
        flash("An error occurred.", "danger")
    return redirect(request.referrer or url_for(".view_community"))


@bp.route("/api/dashboard")
@login_required
def api_dashboard() -> Any:
    """Provide dashboard data as JSON."""
    user_id = g.user["uid"]
    data = UserService.get_dashboard_data(firestore.client(), user_id)
    streak = data["stats"]["current_streak"]
    s_type = data["stats"]["streak_type"]
    return jsonify(
        {
            "user": UserService.get_user_by_id(firestore.client(), user_id),
            "friends": data["friends"],
            "requests": data["requests"],
            "matches": data["matches"],
            "group_rankings": data["group_rankings"],
            "stats": {
                "total_matches": data["stats"]["total_games"],
                "win_percentage": data["stats"]["win_rate"],
                "current_streak": f"{streak}{s_type}" if data["matches"] else "N/A",
            },
        }
    )


@bp.route("/api/create_invite", methods=["POST"])
@login_required
def create_invite() -> Any:
    """Generate a unique invite token."""
    token = UserService.create_invite_token(firestore.client(), g.user["uid"])
    return jsonify({"token": token})