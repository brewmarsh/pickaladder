"""The group blueprint."""

from flask import Blueprint

from .models import Group, Member
from .services.group_service import AccessDenied, GroupNotFound, GroupService
from .services.leaderboard import get_group_leaderboard, get_leaderboard_trend_data
from .services.stats import (
    get_head_to_head_stats,
    get_partnership_stats,
    get_user_group_stats,
)

bp = Blueprint("group", __name__, url_prefix="/group", template_folder="templates")

from . import routes  # noqa: E402

__all__ = [
    "AccessDenied",
    "Group",
    "GroupNotFound",
    "GroupService",
    "Member",
    "get_group_leaderboard",
    "get_leaderboard_trend_data",
    "get_head_to_head_stats",
    "get_partnership_stats",
    "get_user_group_stats",
    "routes",
]
