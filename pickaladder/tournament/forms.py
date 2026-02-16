"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    banner = FileField("Tournament Banner")
    start_date = DateField("Date", validators=[DataRequired()])
    match_type = SelectField(
        "Competition Mode",
        choices=[("SINGLES", "👤 Singles (1v1)"), ("DOUBLES", "👥 Doubles (2v2)")],
        validators=[DataRequired()],
        default="SINGLES",
    )
    venue_name = StringField("Venue Name", validators=[DataRequired()])
    address = StringField("Address")
    description = TextAreaField("Description")


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])
