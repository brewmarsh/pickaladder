"""Forms for the auth blueprint."""

import re

from flask_wtf import FlaskForm  # type: ignore
from wtforms import (
    DecimalField,
    PasswordField,
    StringField,
    SubmitField,
    ValidationError,
)
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


class LoginForm(FlaskForm):
    """Login form."""

    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"autocomplete": "username"},
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
        render_kw={"autocomplete": "current-password"},
    )
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    """Registration form."""

    username = StringField(
        "Username",
        validators=[
            DataRequired(),
            Length(min=3, max=25),
            Regexp(
                r"^[A-Za-z0-9_.]*$",
                message="Username must have only letters, numbers, dots or underscores",
            ),
        ],
    )
    email = StringField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"autocomplete": "email"},
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8),
            EqualTo("confirm_password", message="Passwords must match."),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired()],
        render_kw={"autocomplete": "new-password"},
    )
    name = StringField("Name", validators=[DataRequired()])
    dupr_rating = DecimalField("DUPR Rating", validators=[], places=2)
    submit = SubmitField("Register")

    def validate_password(self, field):
        """Validate password complexity."""
        if not re.search(r"[A-Z]", field.data):
            raise ValidationError(
                "Password must contain at least one uppercase letter."
            )
        if not re.search(r"[a-z]", field.data):
            raise ValidationError(
                "Password must contain at least one lowercase letter."
            )
        if not re.search(r"\d", field.data):
            raise ValidationError("Password must contain at least one number.")
