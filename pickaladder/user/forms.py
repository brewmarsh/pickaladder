from flask_wtf import FlaskForm
from wtforms import DecimalField, FileField, BooleanField, SubmitField
from wtforms.validators import Optional, NumberRange
from flask_wtf.file import FileAllowed


class UpdateProfileForm(FlaskForm):
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
