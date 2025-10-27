"""Forms for the user blueprint."""

from flask_wtf import FlaskForm  # type: ignore
from flask_wtf.file import FileAllowed  # type: ignore
from wtforms import BooleanField, DecimalField, FileField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class UpdateUserForm(FlaskForm):
    """Form for updating user's name, username, and email."""

    name = StringField(
        "Full Name",
        validators=[DataRequired(), Length(min=2, max=50)]
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=2, max=20)]
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()]
    )
    submit = SubmitField("Update Account")


class UpdateProfileForm(FlaskForm):
    """Form for updating a user profile."""

    dupr_rating = DecimalField(
        "DUPR Rating",
        validators=[
            Optional(),
            NumberRange(
                min=2.0,
                max=8.0,
                message="DUPR rating must be between 2.0 and 8.0",
            ),
        ],
        places=2,
    )
    profile_picture = FileField(
        "Update Profile Picture",
        validators=[FileAllowed(["jpg", "jpeg", "png", "gif"], "Images only!")],
    )
    dark_mode = BooleanField("Enable Dark Mode")
    submit = SubmitField("Update Profile")
