"""Utility functions for the group blueprint."""

from __future__ import annotations

import secrets

# Re-exports for backward compatibility
from .services.leaderboard import get_group_leaderboard
from .services.match_parser import _extract_team_ids, _get_match_scores
from .services.stats import (
    get_head_to_head_stats,
    get_leaderboard_trend_data,
    get_partnership_stats,
    get_user_group_stats,
)
from .services.tasks import friend_group_members, send_invite_email_background

__all__ = [
    "get_group_leaderboard",
    "_extract_team_ids",
    "_get_match_scores",
    "get_head_to_head_stats",
    "get_leaderboard_trend_data",
    "get_partnership_stats",
    "get_user_group_stats",
    "friend_group_members",
    "send_invite_email_background",
    "get_random_joke",
]


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
