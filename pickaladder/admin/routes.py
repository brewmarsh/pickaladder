"""Admin routes for the application."""

import datetime
import random
from typing import Union

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
from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService
from pickaladder.user import UserService
from pickaladder.user.models import UserSession

from . import bp
from .services import AdminService

MIN_USERS_FOR_MATCH_GENERATION = 2

# ... (main admin route and other methods remain unchanged)

@bp.route("/generate_matches", methods=["POST"])
@login_required(admin_required=True)
def generate_matches() -> Response:
    """Generate random matches between existing users for testing purposes."""
    db = firestore.client()
    try:
        users = list(db.collection("users").limit(20).stream())
        if len(users) < MIN_USERS_FOR_MATCH_GENERATION:
            flash("Not enough users to generate matches.", "warning")
            return redirect(url_for(".admin"))

        matches_to_create = 10
        matches_created = 0
        
        # We import the helper here to avoid circular dependencies with the User blueprint
        from pickaladder.user.helpers import wrap_user

        for _ in range(matches_to_create):
            p1, p2 = random.sample(users, 2)  # nosec B311
            p1_id = p1.id
            p2_id = p2.id

            # Ensure a valid score (one reaches 11, margin 2)
            s1 = 11
            s2 = random.randint(0, 9)  # nosec B311
            if random.choice([True, False]):  # nosec B311
                s1, s2 = s2, s1

            # Combined approach: Create a typed UserSession then wrap it 
            # to ensure full compatibility with the MatchService logic.
            base_session = UserSession({"uid": p1_id})
            dummy_user = wrap_user(base_session)

            submission = MatchSubmission(
                player_1_id=p1_id,
                player_2_id=p2_id,
                score_p1=s1,
                score_p2=s2,
                match_type="singles",
                match_date=datetime.datetime.now(datetime.timezone.utc),
            )
            
            try:
                if dummy_user:
                    MatchService.record_match(db, submission, dummy_user)
                    matches_created += 1
            except Exception as e:
                # Log specific generation failures without halting the batch
                print(f"Error generating individual match: {e}")

        flash(f"{matches_created} random matches generated successfully.", "success")
    except Exception as e:
        flash(f"An error occurred during match generation: {e}", "danger")

    return redirect(url_for(".admin"))

# ... (remaining routes for merge_players, styleguide, and impersonation remain unchanged)