from flask import Flask, request
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test'
app.config['WTF_CSRF_ENABLED'] = False

class MyForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])

@app.route('/test', methods=['POST'])
def test():
    form = MyForm()
    print(f"Form data: {form.data}")
    print(f"Request form: {request.form}")
    if form.validate_on_submit():
        return "Valid"
    else:
        return f"Invalid: {form.errors}"

with app.test_client() as client:
    response = client.post('/test', data={'name': 'John'})
    print(f"Response: {response.data}")
