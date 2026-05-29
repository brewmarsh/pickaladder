"""Data models for the messaging blueprint."""

from __future__ import annotations

from typing import Any, TypedDict


class Message(TypedDict, total=False):
    """Represents a single message in a conversation."""

    id: str
    senderId: str
    content: str
    timestamp: Any  # Firestore Timestamp
    read: bool


class Conversation(TypedDict, total=False):
    """Represents a conversation between two or more participants."""

    id: str
    participants: list[str]  # Array of user UIDs
    lastMessage: str
    updatedAt: Any  # Firestore Timestamp
    unreadCount: dict[str, int]  # userId -> count
