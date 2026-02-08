"""Team-related utility functions."""

from firebase_admin import firestore

from .services import TeamService


def get_or_create_team(user_a_id, user_b_id):
    """
    Retrieves a team for two users, creating one if it doesn't exist.
    """
    db = firestore.client()
    return TeamService.get_or_create_team(db, user_a_id, user_b_id)
