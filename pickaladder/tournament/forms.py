"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, RadioField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament with secure file uploads."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    
    # RESOLVED: Security validation from main branch
    banner = FileField(
        "Tournament Banner",
        validators=[Optional(), FileAllowed(["jpg", "png", "jpeg"], "Images only!")]
    )
    
    start_date = DateField("Date", validators=[DataRequired()])
    
    # RESOLVED: Optionality from main branch to support fallback logic in routes
    location = StringField("Location", validators=[Optional()])
    venue_name = StringField("Venue Name", validators=[Optional()])
    address = StringField("Address", validators=[Optional()])
    
    # RESOLVED: Compatibility fields for Singles/Doubles selection
    match_type = SelectField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        validators=[Optional()],
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
        default="ROUND_ROBIN",
    )
    
    description = TextAreaField("Description", validators=[Optional()])


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])