"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField
from wtforms.validators import DataRequired


class TournamentForm(FlaskForm):
    """Form for creating a new tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    date = DateField("Date", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired()])
    match_type = SelectField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        validators=[DataRequired()],
    )


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    player = SelectField("Player", validators=[DataRequired()])
