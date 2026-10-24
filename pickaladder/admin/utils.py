import datetime
import random
from typing import Any

from firebase_admin import firestore
from flask import flash, g

from pickaladder.admin.services import AdminService
from pickaladder.constants.messages import ADMIN_MESSAGES, COMMON_MESSAGES
from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService


def generate_single_random_match(db: firestore.Client, users: list[Any]) -> bool:
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
        from pickaladder.user.models import UserSession
        MatchService.record_match(db, submission, UserSession({"uid": p1.id}))
        return True
    except Exception:
        return False

def batch_generate_random_matches(
    db: firestore.Client,
    users: list[Any],
    count: int = 10,
) -> int:
    """Generate multiple random matches and return success count."""
    return sum(1 for _ in range(count) if generate_single_random_match(db, users))

def lookup_user_by_identifier(
    db: firestore.Client,
    identifier: str,
) -> tuple[str | None, str | None]:
    """Look up a user UID and email by their identifier (ID or Email)."""
    user_doc = db.collection("users").document(identifier).get()
    if user_doc.exists:
        return user_doc.id, user_doc.to_dict().get("email")

    users = list(
        db.collection("users")
        .where(filter=firestore.FieldFilter("email", "==", identifier))
        .limit(1)
        .stream(),
    )
    if users:
        return users[0].id, users[0].to_dict().get("email")

    return None, None

def perform_user_deletion(db: firestore.Client, uid: str, email: str | None) -> None:
    """Orchestrate the deletion of a user and flash results."""
    try:
        AdminService.delete_user(db, uid)
        AdminService.log_action(db, g.user.uid, uid, "delete_user", {"email": email})
        flash(
            ADMIN_MESSAGES["USER_DELETED_COUNT"].format(identifier=email or uid),
            "success",
        )
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")

def generate_fake_users(db: firestore.Client, fake: Any) -> list[dict[str, Any]]:
    """Generate fake users logic."""
    from firebase_admin import auth
    new_users = []
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
    return new_users
