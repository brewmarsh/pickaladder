"""Forms for the season blueprint."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DateField, SelectField, StringField
from wtforms.validators import DataRequired


class SeasonForm(FlaskForm):
    """Form for creating or editing a season."""

    name = StringField("Season Name", validators=[DataRequired()])
    start_date = DateField("Start Date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End Date", format="%Y-%m-%d", validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[
            ("DRAFT", "Draft"),
            ("ACTIVE", "Active"),
            ("COMPLETED", "Completed"),
        ],
        default="DRAFT",
        validators=[DataRequired()],
    )
