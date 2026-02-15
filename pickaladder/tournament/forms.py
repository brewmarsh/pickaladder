"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])

    banner = FileField(
        "Tournament Banner",
        validators=[Optional(), FileAllowed(["jpg", "png", "jpeg"], "Images only!")],
    )

    start_date = DateField("Start Date", validators=[DataRequired()])

    # Primary Competition Mode selection
    match_type = SelectField(
        "Competition Type",
        choices=[("SINGLES", "👤 Singles (1v1)"), ("DOUBLES", "👥 Doubles (2v2)")],
        validators=[DataRequired()],
    )

    # Tournament progression style
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

    # --- Legacy Compatibility Fields ---
    # These remain to prevent regressions in older tests or document schemas
    date = DateField("Date (Legacy)", validators=[Optional()])
    location = StringField("Location (Legacy)", validators=[Optional()])
    mode = RadioField(
        "Competition Mode (Legacy)",
        choices=[("SINGLES", "👤 Singles"), ("DOUBLES", "👥 Doubles")],
        validators=[Optional()],
    )


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])