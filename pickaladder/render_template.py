import sys
import os
from flask import Flask, render_template, g
from unittest.mock import MagicMock

# --- Mock Data ---
mock_group = {
    "id": "test_group_id",
    "name": "Test Group",
    "description": "This is a test group for verification.",
    "location": "Virtual",
    "profilePictureUrl": None,
    "ownerRef": MagicMock(id="admin_user_id"),
}

mock_owner = {
    "username": "AdminUser"
}

mock_leaderboard = [
    {
        "id": "user_1",
        "name": "Art Marshall",
        "avg_score": 9.87,
        "games_played": 15,
        "rank_change": 1,
        "form": ["win", "win", "loss", "win", "win"],
        "profilePictureUrl": None,
    },
    {
        "id": "user_2",
        "name": "Betty Rubble",
        "avg_score": 8.50,
        "games_played": 18,
        "rank_change": -1,
        "form": ["loss", "win", "win", "loss", "loss"],
        "profilePictureUrl": None,
    },
    {
        "id": "user_3",
        "name": "Charlie Brown",
        "avg_score": 7.20,
        "games_played": 12,
        "rank_change": 0,
        "form": ["win", "loss", "loss", "win", "loss"],
        "profilePictureUrl": None,
    },
    {
        "id": "user_4",
        "name": "Diana Prince",
        "avg_score": 6.95,
        "games_played": 20,
        "rank_change": "new",
        "form": ["win", "win", "win", "win", "win"],
        "profilePictureUrl": None,
    },
]

mock_current_user_id = "user_1"
mock_user = {"uid": mock_current_user_id}

# --- Flask App for Rendering ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev'

# Add a dummy csrf token function for the template
@app.context_processor
def inject_csrf():
    return dict(csrf_token=lambda: 'dummy_csrf_token')

# Add dummy url_for endpoints to prevent errors
with app.app_context():
    @app.route('/dummy_user/<user_id>')
    def view_user(user_id):
        return ""

    @app.route('/dummy_match')
    def record_match():
        return ""

    @app.route('/dummy_group_edit/<group_id>')
    def edit_group(group_id):
        return ""

    @app.route('/dummy_group_trend/<group_id>')
    def view_leaderboard_trend(group_id):
        return ""

    @app.route('/dummy_dashboard')
    def dashboard():
        return ""

    @app.route('/dummy_users')
    def users():
        return ""

    @app.route('/dummy_login')
    def login():
        return ""

    @app.route('/dummy_logout')
    def logout():
        return ""

    @app.route('/dummy_friends')
    def friends():
        return ""

    @app.route('/dummy_groups')
    def view_groups():
        return ""

    @app.route('/dummy_admin')
    def index():
        return ""

    @app.route('/dummy_leaderboard')
    def leaderboard():
        return ""

    @app.route('/dummy_change_password')
    def change_password():
        return ""

    @app.route('/dummy_register')
    def register():
        return ""

    @app.route('/dummy_reset_password')
    def reset_password():
        return ""

    @app.route('/firebase-config.js')
    def firebase_config():
        return ""


    app.add_url_rule('/user/<user_id>', 'user.view_user', view_user)
    app.add_url_rule('/match/record', 'match.record_match', record_match)
    app.add_url_rule('/group/<group_id>/edit', 'group.edit_group', edit_group)
    app.add_url_rule('/group/<group_id>/leaderboard-trend', 'group.view_leaderboard_trend', view_leaderboard_trend)
    app.add_url_rule('/dashboard', 'user.dashboard', dashboard)
    app.add_url_rule('/users', 'user.users', users)
    app.add_url_rule('/login', 'auth.login', login)
    app.add_url_rule('/logout', 'auth.logout', logout)
    app.add_url_rule('/friends', 'user.friends', friends)
    app.add_url_rule('/groups', 'group.view_groups', view_groups)
    app.add_url_rule('/admin', 'admin.index', index)
    app.add_url_rule('/leaderboard', 'match.leaderboard', leaderboard)
    app.add_url_rule('/change_password', 'auth.change_password', change_password)
    app.add_url_rule('/register', 'auth.register', register)
    app.add_url_rule('/reset_password', 'auth.reset_password', reset_password)
    app.add_url_rule('/firebase-config.js', 'auth.firebase_config', firebase_config)


def render_leaderboard_to_file():
    with app.test_request_context('/'):
        # Set up the global `g` object as the template expects
        g.user = mock_user
        # Mock session object
        g.session = {}

        # Render the template
        rendered_html = render_template(
            "group.html",
            group=mock_group,
            owner=mock_owner,
            leaderboard=mock_leaderboard,
            current_user_id=mock_current_user_id,
            g=g,
            # Add other required dummy data to prevent template errors
            is_member=True,
            members=[],
            form=MagicMock(),
            invite_email_form=MagicMock(),
            pending_invites=[],
        )

        # Read CSS files
        with open("static/style.css", "r") as f:
            style_css = f.read()
        with open("static/mobile.css", "r") as f:
            mobile_css = f.read()

        # Inject CSS into the template
        final_html = rendered_html.replace('</head>', f'<style>{style_css}\n{mobile_css}</style></head>')

        with open("/home/jules/verification/leaderboard.html", "w") as f:
            f.write(final_html)

if __name__ == "__main__":
    render_leaderboard_to_file()
    print("Leaderboard HTML generated successfully.")
