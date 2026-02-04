"""Forms for the match blueprint."""

from flask_wtf import FlaskForm  # type: ignore
from wtforms import (
    DateField,
    HiddenField,
    IntegerField,
    SelectField,
    ValidationError,
)
from wtforms.validators import DataRequired, InputRequired, Optional

MIN_WINNING_SCORE = 11
MIN_WIN_MARGIN = 2


class MatchForm(FlaskForm):
    """Form for recording a new match."""

    match_type = SelectField(
        "Match Type",
        choices=[("singles", "Singles"), ("doubles", "Doubles")],
        default="singles",
        validators=[DataRequired()],
    )
    player1 = SelectField("Team 1 Player 1", validators=[DataRequired()])
    partner = SelectField("Partner", validators=[Optional()])
    player2 = SelectField("Opponent / Opponent 1", validators=[DataRequired()])
    opponent2 = SelectField("Opponent 2", validators=[Optional()])
    player1_score = IntegerField("Your / Team 1 Score", validators=[InputRequired()])
    player2_score = IntegerField(
        "Opponent / Team 2 Score", validators=[InputRequired()]
    )
    match_date = DateField("Date", validators=[DataRequired()])
    group_id = HiddenField("Group ID", validators=[Optional()])
    tournament_id = HiddenField("Tournament ID", validators=[Optional()])

    # TODO: Add type hints for Agent clarity
    def validate_player1_score(self, field):
        """Validate that the score is not negative."""
        if field.data is None:
            return
        if field.data < 0:
            raise ValidationError("Scores cannot be negative.")

    # TODO: Add type hints for Agent clarity
    def validate_player2_score(self, field):
        """Validate that the score is not negative."""
        if field.data is None:
            return
        if field.data < 0:
            raise ValidationError("Scores cannot be negative.")

        if self.player1_score.data is None:
            return

        if field.data == self.player1_score.data:
            raise ValidationError("Scores cannot be the same.")

        p1_score = self.player1_score.data
        p2_score = field.data

        if max(p1_score, p2_score) < MIN_WINNING_SCORE:
            raise ValidationError(
                f"One team/player must have at least {MIN_WINNING_SCORE} points to win."
            )
        if abs(p1_score - p2_score) < MIN_WIN_MARGIN:
            raise ValidationError(
                f"The winner must win by at least {MIN_WIN_MARGIN} points."
            )

    # TODO: Add type hints for Agent clarity
    def validate(self, extra_validators=None):
        """Validate the form for singles or doubles."""
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.match_type.data == "doubles":
            has_error = False
            if not self.partner.data:
                self.partner.errors.append("Partner is required for doubles.")
                has_error = True
            if not self.opponent2.data:
                self.opponent2.errors.append("Opponent 2 is required for doubles.")
                has_error = True

            if has_error:
                return False

            # Check for duplicate players
            players = [
                self.player1.data,
                self.partner.data,
                self.player2.data,
                self.opponent2.data,
            ]
            if len(players) != len(set(players)):
                error_msg = "All players in a doubles match must be unique."
                self.player1.errors.append(error_msg)
                self.partner.errors.append(error_msg)
                self.player2.errors.append(error_msg)
                self.opponent2.errors.append(error_msg)
                return False

        return True
