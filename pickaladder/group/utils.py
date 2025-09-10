from sqlalchemy import or_, case, func
from pickaladder import db
from pickaladder.models import User, Match, FriendGroup


def get_group_leaderboard(group_id):
    """
    Calculates the leaderboard for a specific group.
    """
    group = FriendGroup.query.get(group_id)
    if not group:
        return []

    member_ids = [m.user_id for m in group.members]

    player_score = case(
        (Match.player1_id == User.id, Match.player1_score),
        else_=Match.player2_score,
    )
    leaderboard = (
        db.session.query(
            User.id,
            User.name,
            func.avg(player_score).label("avg_score"),
            func.count(Match.id).label("games_played"),
        )
        .join(Match, or_(User.id == Match.player1_id, User.id == Match.player2_id))
        .filter(User.id.in_(member_ids))
        .filter(Match.player1_id.in_(member_ids))
        .filter(Match.player2_id.in_(member_ids))
        .group_by(User.id, User.name)
        .order_by(func.avg(player_score).desc())
        .all()
    )
    return leaderboard
