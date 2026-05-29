"""Forms for the auth blueprint."""

from __future__ import annotations

import re

from flask_wtf import FlaskForm  # type: ignore
from wtforms import (
    BooleanField,
    DecimalField,
    Field,
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
    remember = BooleanField("Remember me")
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

    # TODO: Add type hints for Agent clarity
    def validate_password(self, field: Field, form: FlaskForm | None = None) -> None:
        """Validate password complexity."""
        if not re.search(r"[A-Z]", field.data):
            msg = "Password must contain at least one uppercase letter."
            raise ValidationError(
                msg,
            )
        if not re.search(r"[a-z]", field.data):
            msg = "Password must contain at least one lowercase letter."
            raise ValidationError(
                msg,
            )
        if not re.search(r"\d", field.data):
            msg = "Password must contain at least one number."
            raise ValidationError(msg)


class ChangePasswordForm(FlaskForm):
    """Form for changing password."""

    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8),
            EqualTo("confirm_password", message="Passwords must match."),
        ],
        render_kw={"autocomplete": "new-password"},
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired()],
        render_kw={"autocomplete": "new-password"},
    )
    submit = SubmitField("Change Password")

    # TODO: Add type hints for Agent clarity
    def validate_password(self, field: Field, form: FlaskForm | None = None) -> None:
        """Validate password complexity."""
        if not re.search(r"[A-Z]", field.data):
            msg = "Password must contain at least one uppercase letter."
            raise ValidationError(
                msg,
            )
        if not re.search(r"[a-z]", field.data):
            msg = "Password must contain at least one lowercase letter."
            raise ValidationError(
                msg,
            )
        if not re.search(r"\d", field.data):
            msg = "Password must contain at least one number."
            raise ValidationError(msg)
