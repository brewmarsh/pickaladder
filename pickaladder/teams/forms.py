"""Forms for the teams blueprint."""

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired


class RenameTeamForm(FlaskForm):
    """Form to rename a team."""

    name = StringField("Team Name", validators=[DataRequired()])
    submit = SubmitField("Rename Team")
