"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    start_date = DateField("Start Date", validators=[DataRequired()])
    # Keep date for backward compatibility in some tests/logic
    date = DateField("Date")
    banner = FileField("Banner Image")
    venue_name = StringField("Venue Name")
    location = StringField("Location")
    address = StringField("Address")
    description = TextAreaField("Description")
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


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])
