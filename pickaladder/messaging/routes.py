"""Routes for the messaging blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .repository import MessagingRepository
from .services import MessagingService


@bp.route("/")
@login_required
def inbox() -> Any:
    """Display user's messaging inbox."""
    db = firestore.client()
    conversations = MessagingService.get_inbox(db, g.user.uid)

    return render_template(
        "messaging/inbox.html",
        conversations=conversations
    )


@bp.route("/chat/<string:conversation_id>")
@login_required
def chat(conversation_id: str) -> Any:
    """View individual conversation."""
    db = firestore.client()
    messages = MessagingRepository.get_messages(db, conversation_id)

    # Verify participant (Quick check, should ideally be in Security Rules)
    conv = MessagingRepository.get_by_id(db, conversation_id)
    if not conv or g.user.uid not in conv.get("participants", []):
        flash("You do not have access to this conversation.", "danger")
        return redirect(url_for(".inbox"))

    return render_template(
        "messaging/chat.html",
        conversation=conv,
        messages=messages
    )


@bp.route("/start/<string:other_user_id>")
@login_required
def start_chat(other_user_id: str) -> Any:
    """Redirect to or create a conversation with another user."""
    db = firestore.client()
    conversation_id = MessagingService.get_or_create_conversation(db, g.user.uid, other_user_id)
    return redirect(url_for(".chat", conversation_id=conversation_id))


@bp.route("/send/<string:conversation_id>", methods=["POST"])
@login_required
def send(conversation_id: str) -> Any:
    """Send a message."""
    db = firestore.client()
    content = request.form.get("content")
    if content:
        MessagingService.send_message(db, conversation_id, g.user.uid, content)

    return redirect(url_for(".chat", conversation_id=conversation_id))
