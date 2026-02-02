"""Forms for the teams blueprint."""

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class EditTeamNameForm(FlaskForm):
    """Form to edit a team's name."""

    name = StringField("Team Name", validators=[DataRequired()])
    submit = SubmitField("Save Changes")
