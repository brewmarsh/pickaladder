import re

with open("pickaladder/group/routes/membership.py", "r") as f:
    content = f.read()

view_group_old = """@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Response | str | dict[str, Any]:
    _handle_referrer()
    db = firestore.client()
    try:
        context = GroupService.get_group_details(
            db,
            group_id,
            g.user.uid,
            request.args.get("playerA"),
            request.args.get("playerB"),
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    invite_email_form, resp = _handle_invite_email_form(
        db, group_id, context["group"].get("name", "Unknown Group")
    )
    if resp:
        return resp

    from pickaladder.season.services import SeasonService

    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)
    return render_template(
        "group.html", form=form, invite_email_form=invite_email_form, **context
    )"""

view_group_new = """@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Response | str | dict[str, Any]:
    _handle_referrer()
    db = firestore.client()
    try:
        context = GroupService.get_group_details(
            db, group_id, g.user.uid, request.args.get("playerA"), request.args.get("playerB")
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp: return resp

    invite_email_form, resp = _handle_invite_email_form(db, group_id, context["group"].get("name", "Unknown Group"))
    if resp: return resp

    from pickaladder.season.services import SeasonService
    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)
    return render_template("group.html", form=form, invite_email_form=invite_email_form, **context)"""

content = content.replace(view_group_old, view_group_new)

with open("pickaladder/group/routes/membership.py", "w") as f:
    f.write(content)
