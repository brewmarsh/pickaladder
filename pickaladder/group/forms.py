"""Forms for the group blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import BooleanField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class GroupForm(FlaskForm):
    """Form for creating a new group."""

    name = StringField("Group Name", validators=[DataRequired()])
    description = TextAreaField("Description")
    is_public = BooleanField("Public Group")
    profile_picture = FileField(
        "Group Profile Picture",
        validators=[FileAllowed(["jpg", "png", "jpeg"]), Optional()],
    )


class InviteFriendForm(FlaskForm):
    """Form for inviting a friend to a group."""

    friend = SelectField("Friend", validators=[DataRequired()])
