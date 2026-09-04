"""Development and testing specific routes for the admin blueprint."""

from __future__ import annotations

import datetime
import random
from typing import Any

from firebase_admin import firestore
from flask import flash, redirect, render_template, request, url_for

from pickaladder.admin import bp
from pickaladder.auth.decorators import login_required
from pickaladder.match.services import MatchService
from pickaladder.user import UserService


@bp.route("/generate_users", methods=["POST"])
@login_required(admin_required=True)
def generate_users() -> Any:  # type: ignore
    """Generate fake users for testing."""
    try:
        from faker import Faker
    except ImportError:
        flash("Faker module is not installed.", "danger")
        return redirect(url_for(".dashboard"))

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
            # Create the user in Auth
            from firebase_admin import auth

            user_record = auth.create_user(email=email, password=password)

            # Create the corresponding user document in Firestore
            user_doc = {
                "uid": user_record.uid,
                "email": email,
                "display_name": fake.user_name(),
                "created_at": firestore.SERVER_TIMESTAMP,
            }
            db.collection("users").document(user_record.uid).set(user_doc)
            new_users.append({"email": email, "password": password})

        flash(f"Successfully created {len(new_users)} test users.", "success")
    except Exception as e:
        flash(f"Error generating users: {e}", "danger")

    return render_template("generated_users.html", users=new_users)


def _generate_single_random_match(db: firestore.Client, users: list[Any]) -> bool:
    """Generate a single random match between users."""
    p1, p2 = random.sample(users, 2)  # nosec B311
    s1, s2 = 11, random.randint(0, 9)  # nosec B311
    if random.choice([True, False]):  # nosec B311
        s1, s2 = s2, s1

    winner_id = p1.id if s1 > s2 else p2.id
    loser_id = p2.id if s1 > s2 else p1.id
    team1 = [{"id": p1.id}]
    team2 = [{"id": p2.id}]

    try:
        # MatchService requires MatchSubmission and UserSession now, or maybe dicts are okay.
        # We will cast them as dict for compatibility.
        match_data = {
            "team1": team1,
            "team2": team2,
            "score1": s1,
            "score2": s2,
            "winner_id": winner_id,
            "loser_id": loser_id,
        }
        MatchService.record_match(db, match_data, {"uid": p1.id, "isAdmin": True})
        return True
    except Exception:
        return False


def _batch_generate_random_matches(
    db: firestore.Client,
    users: list[Any],
    count: int = 10,
) -> int:
    """Generate multiple random matches sequentially."""
    return sum(1 for _ in range(count) if _generate_single_random_match(db, users))


@bp.route("/generate_matches", methods=["POST"])
@login_required(admin_required=True)
def generate_matches() -> Any:  # type: ignore
    """Generate random matches between existing users."""
    db = firestore.client()
    try:
        count = int(request.form.get("count", 10))
        users = list(db.collection("users").stream())
        if len(users) < 2:
            flash("Need at least 2 users to generate matches.", "warning")
            return redirect(url_for(".dashboard"))

        successful_matches = _batch_generate_random_matches(db, users, count)
        flash(f"Successfully generated {successful_matches} matches.", "success")
    except Exception as e:
        flash(f"Error generating matches: {e}", "danger")

    return redirect(url_for(".dashboard"))


@bp.route("/merge_players", methods=["GET", "POST"])
@login_required(admin_required=True)
def merge_players() -> Any:
    """Merge two player accounts (Source -> Target)."""
    db = firestore.client()
    if request.method == "POST":
        source_id = request.form.get("source_id")
        target_id = request.form.get("target_id")

        if not source_id or not target_id:
            flash("Both source and target user IDs are required.", "danger")
            return redirect(url_for(".merge_players"))

        if source_id == target_id:
            flash("Source and target user IDs cannot be the same.", "danger")
            return redirect(url_for(".merge_players"))

        try:
            UserService.merge_ghost_user(
                db, db.collection("users").document(target_id), source_id
            )  # type: ignore
            flash(
                f"Successfully merged data from user {source_id} to user {target_id}.",
                "success",
            )
        except Exception as e:
            flash(f"Error merging players: {e}", "danger")

        return redirect(url_for(".merge_players"))

    return render_template("admin/merge_players.html")


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
