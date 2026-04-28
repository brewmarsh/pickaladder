"""Profile and Dashboard routes for the user blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore
from flask import (
    Response,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import USER_MESSAGES
from pickaladder.core.activity.services import ActivityService
from pickaladder.core.constants import DUPR_PROFILE_BASE_URL
from pickaladder.group.services.group_service import GroupService
from pickaladder.group.services.leaderboard import get_leaderboard_trend_data
from pickaladder.season.analytics import AnalyticsService

from .. import bp
from ..forms import SettingsForm, UpdateUserForm
from ..services import UserService

if TYPE_CHECKING:
    pass


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings() -> Response | str:
    """Unified user settings page."""
    db = firestore.client()
    user_id = g.user.uid
    form = SettingsForm()

    if request.method == "GET":
        form.name.data = g.user.get("name")
        form.username.data = g.user.get("username")
        form.email.data = g.user.get("email")
        form.dupr_id.data = g.user.get("dupr_id")
        form.dupr_rating.data = g.user.get("duprRating") or g.user.get("dupr_rating")
        form.dark_mode.data = g.user.get("dark_mode")

    if form.validate_on_submit():
        # Use the consolidated service call
        res = UserService.process_profile_update(
            db, user_id, form, g.user, form.profile_picture.data
        )

        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash(USER_MESSAGES["SETTINGS_UPDATED"], "success")
            return redirect(url_for(".settings"))
        flash(res["error"], "danger")

    return render_template("user/settings.html", form=form, user=g.user)


@bp.route("/settings/reset_avatar", methods=["POST"])
@login_required
def reset_avatar() -> Response:
    """Reset the user's avatar to default."""
    db = firestore.client()
    user_id = g.user.uid
    if UserService.reset_profile_picture(db, user_id):
        flash(USER_MESSAGES["PROFILE_PIC_REMOVED"], "success")
    else:
        flash(USER_MESSAGES["PROFILE_PIC_REMOVE_ERROR"], "danger")
    return redirect(url_for(".settings"))


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile() -> Response | str:
    """Handle user profile updates."""
    form = UpdateUserForm(data=g.user)
    if form.validate_on_submit():
        res = UserService.process_profile_update(
            firestore.client(), g.user.uid, form, g.user
        )
        if res["success"]:
            if "info" in res:
                flash(res["info"], "info")
            flash(USER_MESSAGES["ACCOUNT_UPDATED"], "success")
            return redirect(url_for(".edit_profile"))
        flash(res["error"], "danger")
    return render_template("user/edit_profile.html", form=form, user=g.user)


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """Render user dashboard."""
    db = firestore.client()
    user_id = g.user.uid

    data = UserService.get_dashboard_data(db, user_id)

    # Fetch community activity feed
    feed = ActivityService.get_global_feed(db, limit=10)

    # Remove user from data to avoid conflict with g.user passed to template
    data.pop("user", None)

    return render_template(
        "user_dashboard.html",
        user=g.user,
        feed=feed,
        **data,
    )


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id: str) -> Response | str:
    """Display a user's public profile."""
    db = firestore.client()
    data = UserService.get_user_profile_data(db, g.user.uid, user_id)
    if not data:
        flash(USER_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".users"))

    stats = data.get("stats", {})
    total_games = stats.get("total_games", 0)

    # Fetch historical performance from completed seasons
    season_history = AnalyticsService.get_user_season_history(db, user_id)
    achievements = AnalyticsService.get_user_achievements(season_history)

    return render_template(
        "user/profile.html",
        user=g.user,
        dupr_url_base=DUPR_PROFILE_BASE_URL,
        record={"wins": stats.get("wins", 0), "losses": stats.get("losses", 0)},
        total_games=total_games,
        win_rate=stats.get("win_rate", 0),
        current_streak=stats.get("current_streak", 0),
        streak_type=stats.get("streak_type", "N/A"),
        season_history=season_history,
        achievements=achievements,
        **data,
    )


@bp.route("/share/brag/<user_id>/<group_id>")
def share_brag(user_id: str, group_id: str) -> Response | str:
    """Publicly shareable Brag Card."""
    db = firestore.client()

    # Fetch user data
    user_doc = db.collection("users").document(user_id).get()
    if not user_doc.exists:
        flash(USER_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("main.index"))
    user_data = user_doc.to_dict() or {}

    # Fetch group data
    group_doc = db.collection("groups").document(group_id).get()
    if not group_doc.exists:
        flash("Group not found", "danger")
        return redirect(url_for("main.index"))
    group_data = group_doc.to_dict() or {}
    group_data["id"] = group_id

    # Fetch leaderboard to get rank and streak
    # We use user_id as the requester since this is public
    details = GroupService.get_group_details(db, group_id, user_id)
    leaderboard = details.get("leaderboard", [])

    user_stats = next((p for p in leaderboard if p["id"] == user_id), None)
    if not user_stats:
        flash("User not part of this group", "danger")
        return redirect(url_for("main.index"))

    rank = next((i + 1 for i, p in enumerate(leaderboard) if p["id"] == user_id), 0)
    streak = user_stats.get("streak", 0)

    # Fetch trend data
    trend_data_all = get_leaderboard_trend_data(group_id)
    user_dataset = next(
        (ds for ds in trend_data_all["datasets"] if ds.get("id") == user_id),
        {"data": []},
    )

    avatar_url = user_data.get("profilePictureUrl")
    if not avatar_url:
        avatar_url = url_for("static", filename="user_icon.png", _external=True)

    return render_template(
        "share/brag_card.html",
        user_name=user_data.get("username", "Unknown"),
        group=group_data,
        rank=rank,
        streak=streak,
        trend_data=user_dataset.get("data", []),
        avatar_url=avatar_url,
    )
