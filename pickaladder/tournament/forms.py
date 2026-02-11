"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from wtforms import DateField, RadioField, SelectField, StringField
from wtforms.validators import DataRequired


class TournamentForm(FlaskForm):
    """Form for creating a new tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    date = DateField("Date", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired()])
    mode = RadioField(
        "Competition Mode",
        choices=[("SINGLES", "👤 Singles (1v1)"), ("DOUBLES", "👥 Doubles (2v2)")],
        validators=[DataRequired()],
        default="SINGLES",
    )


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])
