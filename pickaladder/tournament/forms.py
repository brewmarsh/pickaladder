"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[DataRequired()])
    venue_name = StringField("Venue Name", validators=[DataRequired()])
    address = StringField("Address", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[Optional()])
    banner = FileField(
        "Event Banner (16:9 recommended)",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only!")],
    )
    match_type = SelectField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        validators=[DataRequired()],
    )
    format = SelectField(
        "Tournament Format",
        choices=[
            ("ROUND_ROBIN", "Round Robin"),
            ("SINGLE_ELIMINATION", "Single Elimination"),
        ],
        validators=[DataRequired()],
    )


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])
