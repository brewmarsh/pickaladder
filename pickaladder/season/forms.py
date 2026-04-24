"""Forms for the season blueprint."""

from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import DateField, IntegerField, SelectField, StringField
from wtforms.validators import DataRequired, NumberRange


class SeasonForm(FlaskForm):
    """Form for creating or editing a season."""

    name = StringField("Season Name", validators=[DataRequired()])
    start_date = DateField("Start Date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End Date", format="%Y-%m-%d", validators=[DataRequired()])
    promotion_count = IntegerField(
        "Promotion Count",
        default=0,
        validators=[NumberRange(min=0)]
    )
    relegation_count = IntegerField(
        "Relegation Count",
        default=0,
        validators=[NumberRange(min=0)]
    )
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
