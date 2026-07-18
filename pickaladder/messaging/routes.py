"""Routes for the messaging blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import Response, flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .repository import MessagingRepository
from .services import MessagingService


@bp.route("/")
@login_required
def inbox() -> str:
    """Display user's messaging inbox."""
    db = firestore.client()
    conversations = MessagingService.get_inbox(db, g.user.uid)

    return render_template("messaging/inbox.html", conversations=conversations)


@bp.route("/chat/<string:conversation_id>")
@login_required
def chat(conversation_id: str) -> Response | str:
    """View individual conversation."""
    db = firestore.client()
    messages = MessagingRepository.get_messages(db, conversation_id)

    # Verify participant (Quick check, should ideally be in Security Rules)
    conv = MessagingRepository.get_by_id(db, conversation_id)
    if not conv or g.user.uid not in conv.get("participants", []):
        flash("You do not have access to this conversation.", "danger")
        return redirect(url_for(".inbox"))  # type: ignore

    # Mark as read
    MessagingService.mark_as_read(db, conversation_id, g.user.uid)

    return render_template("messaging/chat.html", conversation=conv, messages=messages)


@bp.route("/start/<string:other_user_id>")
@login_required
def start_chat(other_user_id: str) -> Response:
    """Redirect to or create a conversation with another user."""
    db = firestore.client()
    conversation_id = MessagingService.get_or_create_conversation(
        db,
        g.user.uid,
        other_user_id,
    )
    return redirect(url_for(".chat", conversation_id=conversation_id))  # type: ignore


@bp.route("/send/<string:conversation_id>", methods=["POST"])
@login_required
def send(conversation_id: str) -> Response:
    """Send a message."""
    db = firestore.client()

    # Verify participant to prevent IDOR
    conv = MessagingRepository.get_by_id(db, conversation_id)
    if not conv or g.user.uid not in conv.get("participants", []):
        flash(
            "You do not have permission to send messages in this conversation.",
            "danger",
        )
        return redirect(url_for(".inbox"))  # type: ignore

    content = request.form.get("content")
    if content:
        MessagingService.send_message(db, conversation_id, g.user.uid, content)

    return redirect(url_for(".chat", conversation_id=conversation_id))  # type: ignore


@bp.route("/broadcast/<string:group_id>", methods=["POST"])
@login_required
def broadcast(group_id: str) -> Response:
    """Broadcast an announcement to all group members."""
    from pickaladder.group.repository import GroupRepository
    from pickaladder.group.services.group_service import GroupService

    db = firestore.client()
    group = GroupRepository.get_by_id(db, group_id)
    if not group:
        flash("Group not found.", "danger")
        return redirect(url_for("main.index"))  # type: ignore

    # Verify permissions (must be admin/owner)
    if not GroupService.is_group_admin(group, g.user.uid):
        flash("You do not have permission to broadcast to this group.", "danger")
        return redirect(url_for("group.manage_group", group_id=group_id))  # type: ignore

    content = request.form.get("content")
    if content:
        # Fetch all member IDs
        member_refs = group.get("members", [])
        member_ids = [ref.id for ref in member_refs]

        owner_id = group.get("ownerRef").id if group.get("ownerRef") else g.user.uid  # type: ignore

        # Get or create announcement conversation
        conversation_id = MessagingService.get_or_create_group_announcement(
            db,
            group_id,
            owner_id,
            member_ids,
        )

        # Send the message
        MessagingService.send_message(db, conversation_id, g.user.uid, content)

        flash("Announcement broadcasted successfully!", "success")

    return redirect(url_for("group.manage_group", group_id=group_id))  # type: ignore
