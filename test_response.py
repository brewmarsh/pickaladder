from flask import Flask, Response, jsonify

app = Flask(__name__)

with app.app_context():
    r = jsonify({"error": "Faker module is not installed."})
    print(type(r))
    print(isinstance(r, Response))
