"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    start_date = DateField("Date", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired()])
    venue_name = StringField("Venue Name", validators=[Optional()])
    address = StringField("Address", validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional()])
    banner = FileField(
        "Tournament Banner",
        validators=[FileAllowed(["jpg", "png", "jpeg"], "Images only!")],
    )
    match_type = RadioField(
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
    )


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])
