from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    g
)
from db import get_db_connection
from . import bp
import psycopg2
from psycopg2 import errors
from faker import Faker
import random
import string
from werkzeug.security import generate_password_hash
from pickaladder import mail
from flask_mail import Message
import uuid

@bp.before_request
def before_request():
    if not session.get('is_admin'):
        return redirect(url_for('auth.login'))

@bp.route('/')
def admin():
    return render_template('admin.html')

@bp.route('/matches')
def admin_matches():
    search_term = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    if search_term:
        cur.execute(
            'SELECT m.*, p1.username, p2.username FROM matches m '
            'JOIN users p1 ON m.player1_id = p1.id '
            'JOIN users p2 ON m.player2_id = p2.id '
            'WHERE p1.username ILIKE %s OR p2.username ILIKE %s '
            'ORDER BY m.match_date DESC',
            (f'%{search_term}%', f'%{search_term}%'),
        )
    else:
        cur.execute(
            'SELECT m.*, p1.username, p2.username FROM matches m '
            'JOIN users p1 ON m.player1_id = p1.id '
            'JOIN users p2 ON m.player2_id = p2.id ORDER BY m.match_date DESC'
        )
    matches = cur.fetchall()
    return render_template(
        'admin_matches.html', matches=matches, search_term=search_term
    )

@bp.route('/delete_match/<string:match_id>')
def admin_delete_match(match_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM matches WHERE id = %s', (match_id,))
        conn.commit()
        flash('Match deleted successfully.', 'success')
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
    return redirect(url_for('.admin_matches'))

@bp.route('/friend_graph_data')
def friend_graph_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT id, username FROM users")
    users = cur.fetchall()
    cur.execute("SELECT user_id, friend_id FROM friends WHERE status = 'accepted'")
    friends = cur.fetchall()

    nodes = [{"id": str(user['id']), "label": user['username']} for user in users]
    edges = [{"from": str(friend['user_id']), "to": str(friend['friend_id'])} for friend in friends]

    return jsonify({"nodes": nodes, "edges": edges})

@bp.route('/reset_db')
def reset_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('TRUNCATE TABLE friends, users, matches CASCADE')
    conn.commit()
    return redirect(url_for('.admin'))

@bp.route('/reset-admin', methods=['GET', 'POST'])
def reset_admin():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Reset all users to not be admin
        cur.execute("UPDATE users SET is_admin = FALSE")
        # Set the first user to be admin
        cur.execute(
            "UPDATE users SET is_admin = TRUE WHERE id = (SELECT id FROM users ORDER BY id LIMIT 1)"
        )
        conn.commit()
        return redirect(url_for('.admin'))

    return render_template('reset_admin.html')

@bp.route('/delete_user/<uuid:user_id>')
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM friends WHERE user_id = %s OR friend_id = %s',
            (user_id, user_id),
        )
        cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
        conn.commit()
        flash('User deleted successfully.', 'success')
    except errors.ForeignKeyViolation as e:
        flash(f"Cannot delete user: {e}", 'danger')
        return render_template('error.html', error=f"Cannot delete user: {e}"), 500
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
        return render_template('error.html', error=str(e)), 500
    return redirect(url_for('user.users'))

@bp.route('/promote_user/<uuid:user_id>')
def promote_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = TRUE WHERE id = %s', (user_id,))
    conn.commit()
    return redirect(url_for('user.users'))

@bp.route('/reset_password/<uuid:user_id>')
def admin_reset_password(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT email FROM users WHERE id = %s', (user_id,))
        email = cur.fetchone()[0]
        new_password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cur.execute(
            'UPDATE users SET password = %s WHERE id = %s', (hashed_password, user_id)
        )
        conn.commit()
        msg = Message(
            'Your new password',
            sender=current_app.config['MAIL_USERNAME'],
            recipients=[email],
        )
        msg.body = f'Your new password is: {new_password}'
        mail.send(msg)
        flash('Password reset successfully and sent to the user.', 'success')
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
    return redirect(url_for('user.users'))

@bp.route('/generate_users')
def generate_users():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT username FROM users')
    existing_usernames = {row[0] for row in cur.fetchall()}
    fake = Faker()
    new_users = []

    for _ in range(10):
        name = fake.name()
        username = name.lower().replace(" ", "")
        if username in existing_usernames:
            continue
        password = 'password'
        email = f'{username}@example.com'
        dupr_rating = round(
            fake.pyfloat(
                left_digits=1, right_digits=2, positive=True, min_value=1.0, max_value=5.0
            ),
            2,
        )
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        cur.execute(
            'INSERT INTO users (username, password, email, name, dupr_rating, is_admin) '
            'VALUES (%s, %s, %s, %s, %s, %s) '
            'RETURNING id, username, email, name, dupr_rating',
            (username, hashed_password, email, name, dupr_rating, False),
        )
        new_user = cur.fetchone()
        new_users.append(new_user)
    conn.commit()

    # Add random friendships
    for i in range(len(new_users)):
        for j in range(i + 1, len(new_users)):
            if random.random() < 0.5:
                cur.execute(
                    'INSERT INTO friends (user_id, friend_id, status) VALUES (%s, %s, %s)',
                    (new_users[i][0], new_users[j][0], 'accepted'),
                )
    conn.commit()

    return render_template('generated_users.html', users=new_users)

@bp.route('/generate_matches')
def generate_matches():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Get all friendships
        cur.execute("SELECT user_id, friend_id FROM friends WHERE status = 'accepted'")
        friends = cur.fetchall()

        if not friends:
            flash('No friendships found to generate matches.', 'warning')
            return redirect(url_for('.admin'))

        # Generate 10 random matches
        for _ in range(10):
            user_id, friend_id = random.choice(friends)

            # Generate scores
            score1 = random.randint(0, 11)
            if score1 >= 10:
                score2 = score1 - 2
            else:
                score2 = random.randint(0, 11)
                while abs(score1 - score2) < 2 and max(score1, score2) >= 11:
                    score2 = random.randint(0, 11)

            # Randomly assign scores to players
            if random.random() < 0.5:
                player1_score, player2_score = score1, score2
            else:
                player1_score, player2_score = score2, score1

            # Insert match
            match_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO matches (id, player1_id, player2_id, player1_score, player2_score, match_date) '
                'VALUES (%s, %s, %s, %s, %s, NOW())',
                (
                    match_id,
                    user_id,
                    friend_id,
                    player1_score,
                    player2_score,
                ),
            )

        conn.commit()
        flash('10 random matches generated successfully.', 'success')

    except Exception as e:
        conn.rollback()
        flash(f"An error occurred while generating matches: {e}", 'danger')

    return redirect(url_for('.admin'))
