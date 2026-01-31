"""Team-related utility functions."""

from firebase_admin import firestore


def get_or_create_team(user_a_id, user_b_id):
    """
    Retrieves a team for two users, creating one if it doesn't exist.
    """
    db = firestore.client()
    # Sort IDs to ensure the query is consistent regardless of order
    member_ids = sorted([user_a_id, user_b_id])

    # Query for an existing team with the exact same members
    teams_ref = db.collection("teams")
    query = teams_ref.where(
        filter=firestore.FieldFilter("member_ids", "==", member_ids)
    )
    docs = list(query.stream())

    if docs:
        # Team already exists, return its ID
        return docs[0].id
    else:
        # Team does not exist, so create it
        user_a_ref = db.collection("users").document(user_a_id)
        user_b_ref = db.collection("users").document(user_b_id)

        user_a_doc = user_a_ref.get()
        user_b_doc = user_b_ref.get()

        user_a_name = user_a_doc.to_dict().get("name", "Player A")
        user_b_name = user_b_doc.to_dict().get("name", "Player B")

        new_team_data = {
            "member_ids": member_ids,
            "members": [user_a_ref, user_b_ref],
            "name": f"{user_a_name} & {user_b_name}",
            "stats": {"wins": 0, "losses": 0, "elo": 1200},
            "created_at": firestore.SERVER_TIMESTAMP,
        }
        # Add the new team to the 'teams' collection
        new_team_ref = teams_ref.document()
        new_team_ref.set(new_team_data)
        return new_team_ref.id
