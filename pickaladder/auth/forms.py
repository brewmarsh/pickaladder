from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

from wtforms import DecimalField, ValidationError
from wtforms.validators import Length, Email, EqualTo, Regexp
import re


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=25),
            Regexp(
                r"^[A-Za-z0-9_.]*$",
                message="Username must have only letters, numbers, dots or "
                "underscores",
            ),
        ],
    )
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8),
            EqualTo("confirm_password", message="Passwords must match."),
        ],
    )
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    dupr_rating = DecimalField("DUPR Rating", validators=[], places=2)
    submit = SubmitField("Register")

    def validate_password(self, field):
        if not re.search(r"[A-Z]", field.data):
            raise ValidationError(
                "Password must contain at least one " "uppercase letter."
            )
        if not re.search(r"[a-z]", field.data):
            raise ValidationError(
                "Password must contain at least one " "lowercase letter."
            )
        if not re.search(r"\d", field.data):
            raise ValidationError("Password must contain at least one number.")
