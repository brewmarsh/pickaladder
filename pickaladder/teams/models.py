"""Data models for the teams feature."""

from firebase_admin import firestore


def create_team_document(db, team_members):
    """
    Creates a new team document in Firestore.

    Args:
        db: The Firestore client.
        team_members (list): A list of user document references for the team members.

    Returns:
        The new team document reference.
    """
    sorted_members = sorted(team_members, key=lambda doc_ref: doc_ref.id)
    member_ids = [doc_ref.id for doc_ref in sorted_members]
    member_names = [
        doc_ref.get().to_dict().get("name", "Unknown") for doc_ref in sorted_members
    ]
    team_name = " & ".join(member_names)

    team_data = {
        "members": sorted_members,
        "member_ids": member_ids,
        "name": team_name,
        "stats": {"wins": 0, "losses": 0, "elo": 1200},
        "created_at": firestore.SERVER_TIMESTAMP,
    }

    team_ref = db.collection("teams").add(team_data)
    return team_ref[1]
