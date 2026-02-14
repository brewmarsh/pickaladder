"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from wtforms import DateField, FileField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    start_date = DateField("Date", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired()])
    venue_name = StringField("Venue Name")
    address = StringField("Address")
    description = TextAreaField("Description")
    banner = FileField("Banner Image")
    match_type = SelectField(
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
