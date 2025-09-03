from flask_wtf import FlaskForm  # type: ignore
from wtforms import SelectField, IntegerField, DateField, ValidationError
from wtforms.validators import DataRequired


class MatchForm(FlaskForm):
    player2 = SelectField("Opponent", validators=[DataRequired()])
    player1_score = IntegerField("Your Score", validators=[DataRequired()])
    player2_score = IntegerField("Opponent's Score", validators=[DataRequired()])
    match_date = DateField("Date", validators=[DataRequired()])

    def validate_player1_score(self, field):
        if field.data < 0:
            raise ValidationError("Scores cannot be negative.")

    def validate_player2_score(self, field):
        if field.data < 0:
            raise ValidationError("Scores cannot be negative.")

        # This validation depends on player1_score, if it's not present, we
        # can't validate.
        # The DataRequired validator on player1_score should prevent this state.
        if self.player1_score.data is None:
            return

        if field.data == self.player1_score.data:
            raise ValidationError("Scores cannot be the same.")

        p1_score = self.player1_score.data
        p2_score = field.data

        if max(p1_score, p2_score) < 11:
            raise ValidationError("One player must have at least 11 points to win.")
        if abs(p1_score - p2_score) < 2:
            raise ValidationError("The winner must win by at least 2 points.")
