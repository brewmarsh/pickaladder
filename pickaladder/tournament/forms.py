"""Forms for the tournament blueprint."""

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import DateField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Optional


class TournamentForm(FlaskForm):
    """Form for creating/editing a tournament."""

    name = StringField("Tournament Name", validators=[DataRequired()])
    
    banner = FileField(
        "Tournament Banner",
        validators=[Optional(), FileAllowed(["jpg", "png", "jpeg"], "Images only!")],
    )
    
    start_date = DateField("Start Date", validators=[Optional()])
    
    # Legacy field for backward compatibility with older tests/automation
    date = DateField("Date", validators=[Optional()])

    # Competition Type selection
    match_type = SelectField(
        "Match Type",
        choices=[
            ("SINGLES", "👤 Singles (1v1)"), 
            ("DOUBLES", "👥 Doubles (2v2)"),
            ("singles", "👤 Singles (1v1)"),
            ("doubles", "👥 Doubles (2v2)")
        ],
        validators=[Optional()],
        default="SINGLES",
    )

    # Alias for match_type to support legacy routes
    mode = SelectField(
        "Competition Mode",
        choices=[
            ("SINGLES", "👤 Singles (1v1)"), 
            ("DOUBLES", "👥 Doubles (2v2)"),
            ("singles", "👤 Singles (1v1)"),
            ("doubles", "👥 Doubles (2v2)")
        ],
        validators=[Optional()],
        default="SINGLES",
    )

    format = SelectField(
        "Tournament Format",
        choices=[
            ("ROUND_ROBIN", "Round Robin"),
            ("SINGLE_ELIMINATION", "Single Elimination"),
        ],
        validators=[DataRequired()],
        default="ROUND_ROBIN"
    )

    # Location Metadata for Maps Integration
    venue_name = StringField("Venue Name", validators=[Optional()])
    address = StringField("Address (for directions)", validators=[Optional()])
    
    # Legacy location field
    location = StringField("Location", validators=[Optional()])

    description = TextAreaField("Description", validators=[Optional()])


class InvitePlayerForm(FlaskForm):
    """Form for inviting a player to a tournament."""

    user_id = SelectField("Player", validators=[DataRequired()])