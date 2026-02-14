"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    
    start_date = DateField("Start Date", validators=[DataRequired()])
    
    venue_name = StringField("Venue Name", validators=[DataRequired()])
    
    address = StringField("Address", validators=[DataRequired()])

    description = TextAreaField("Description", validators=[Optional()])

    match_type = SelectField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        validators=[DataRequired()],
    )

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
    )

    banner = FileField(
        "Tournament Banner",
        validators=[
            Optional(),
            FileAllowed(["jpg", "jpeg", "png", "webp"], "Images only!"),
        ],
    )

    # Legacy fields for backward compatibility with existing Firestore documents
    date = DateField("Date (Legacy)", validators=[Optional()])
    location = StringField("Location (Legacy)", validators=[Optional()])


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])