"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])

    banner = FileField(
        "Banner Image",
        validators=[Optional(), FileAllowed(["jpg", "png", "jpeg"], "Images only!")],
    )

    start_date = DateField("Start Date", validators=[DataRequired()])

    match_type = RadioField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        validators=[Optional()],
        default="singles",
    )

    mode = RadioField(
        "Competition Mode",
        choices=[("SINGLES", "👤 Singles (1v1)"), ("DOUBLES", "👥 Doubles (2v2)")],
        validators=[DataRequired()],
        default="SINGLES",
    )

    format = SelectField(
        "Tournament Format",
        choices=[
            ("ROUND_ROBIN", "Round Robin"),
            ("SINGLE_ELIMINATION", "Single Elimination"),
        ],
        validators=[DataRequired()],
        default="ROUND_ROBIN",
    )

    venue_name = StringField("Venue Name", validators=[Optional()])

    address = StringField("Address", validators=[Optional()])

    description = TextAreaField("Description", validators=[Optional()])

    # Legacy fields for compatibility with older tests and document schemas
    date = DateField("Date (Legacy)", validators=[Optional()])
    location = StringField("Location (Legacy)", validators=[Optional()])


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])