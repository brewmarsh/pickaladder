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
        validators=[Optional(), FileAllowed(["jpg", "png", "jpeg"])],
    )

    # Date handling with backward compatibility
    start_date = DateField("Start Date", validators=[Optional()])
    date = DateField("Date", validators=[Optional()])

    # Competition Mode handling (SelectField and RadioField for UI flexibility)
    match_type = SelectField(
        "Competition Mode",
        choices=[
            ("SINGLES", "👤 Singles (1v1)"),
            ("DOUBLES", "👥 Doubles (2v2)"),
            ("singles", "👤 Singles (1v1)"),
            ("doubles", "👥 Doubles (2v2)"),
        ],
        validators=[Optional()],
    )

    mode = RadioField(
        "Competition Mode",
        choices=[
            ("SINGLES", "👤 Singles (1v1)"),
            ("DOUBLES", "👥 Doubles (2v2)"),
            ("singles", "👤 Singles (1v1)"),
            ("doubles", "👥 Doubles (2v2)"),
        ],
        validators=[Optional()],
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

    # Location handling
    venue_name = StringField("Venue Name", validators=[Optional()])
    address = StringField("Address", validators=[Optional()])
    location = StringField("Location", validators=[Optional()])

    description = TextAreaField("Description", validators=[Optional()])


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])