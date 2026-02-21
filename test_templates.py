from flask import Flask, render_template

app = Flask(__name__, template_folder="pickaladder/templates")


@app.route("/")
def test():
    return render_template(
        "tournament/view.html",
        tournament={"id": "1", "name": "Test"},
        is_owner=True,
        invite_form=None,
    )


with app.test_request_context():
    try:
        app.jinja_env.get_template("tournament/view.html")
        print("tournament/view.html is OK")
    except Exception as e:
        print(f"tournament/view.html Error: {e}")

    try:
        app.jinja_env.get_template("tournaments/create_edit.html")
        print("tournaments/create_edit.html is OK")
    except Exception as e:
        print(f"tournaments/create_edit.html Error: {e}")

    try:
        app.jinja_env.get_template("navbar.html")
        print("navbar.html is OK")
    except Exception as e:
        print(f"navbar.html Error: {e}")
