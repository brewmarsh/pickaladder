from flask_wtf import FlaskForm
from wtforms import StringField, SelectField
from wtforms.validators import DataRequired


class FriendGroupForm(FlaskForm):
    name = StringField("Group Name", validators=[DataRequired()])


class InviteFriendForm(FlaskForm):
    friend = SelectField("Friend", validators=[DataRequired()])
