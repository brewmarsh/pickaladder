"""Utility functions for the group blueprint."""

from __future__ import annotations

import secrets

# Re-exports for backward compatibility
from .services.leaderboard import get_group_leaderboard as get_group_leaderboard
from .services.match_parser import _extract_team_ids as _extract_team_ids
from .services.match_parser import _get_match_scores as _get_match_scores
from .services.stats import (
    get_head_to_head_stats as get_head_to_head_stats,
)
from .services.stats import (
    get_leaderboard_trend_data as get_leaderboard_trend_data,
)
from .services.stats import (
    get_partnership_stats as get_partnership_stats,
)
from .services.stats import (
    get_user_group_stats as get_user_group_stats,
)
from .services.tasks import friend_group_members as friend_group_members
from .services.tasks import (
    send_invite_email_background as send_invite_email_background,
)


def get_random_joke() -> str:
    """Return a random sport/dad joke."""
    jokes = [
        "Why did the pickleball player get arrested? Because he was caught smashing!",
        "What do you call a girl standing in the middle of a tennis court? Annette.",
        (
            "Why are fish never good at tennis? Because they don't like getting "
            "close to the net."
        ),
        "What is a tennis player's favorite city? Volley-wood.",
        "Why do tennis players never get married? Because love means nothing to them.",
        "What time does a tennis player go to bed? Ten-ish.",
        (
            "Why did the pickleball hit the net? It wanted to see what was on the "
            "other side."
        ),
        "How is a pickleball game like a waiter? They both serve.",
        (
            "Why should you never fall in love with a tennis player? To them, 'Love' "
            "means nothing."
        ),
        "What do you serve but not eat? A tennis ball.",
    ]
    return secrets.choice(jokes)
