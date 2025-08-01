from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    g,
    current_app,
)
from pickaladder.db import get_db_connection
from . import bp
import psycopg2
import psycopg2.extras
from psycopg2 import errors
from faker import Faker
import random
import string
from werkzeug.security import generate_password_hash
from pickaladder import mail
from flask_mail import Message
import uuid
from pickaladder.constants import (
    USERS_TABLE,
    FRIENDS_TABLE,
    MATCHES_TABLE,
    USER_ID,
    USER_USERNAME,
    USER_IS_ADMIN,
    FRIENDS_USER_ID,
    FRIENDS_FRIEND_ID,
    FRIENDS_STATUS,
    MATCH_ID,
    MATCH_PLAYER1_ID,
    MATCH_PLAYER2_ID,
    MATCH_DATE,
    USER_EMAIL,
    USER_PASSWORD,
    USER_NAME,
    USER_DUPR_RATING,
    MATCH_PLAYER1_SCORE,
    MATCH_PLAYER2_SCORE,
)

@bp.before_request
def before_request():
    if not session.get(USER_IS_ADMIN):
        return redirect(url_for('auth.login'))

@bp.route('/')
def admin():
    return render_template('admin.html')

@bp.route(f'/{MATCHES_TABLE}')
def admin_matches():
    search_term = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    if search_term:
        cur.execute(
            f'SELECT m.*, p1.{USER_USERNAME}, p2.{USER_USERNAME} '
            f'FROM {MATCHES_TABLE} m '
            f'JOIN {USERS_TABLE} p1 ON m.{MATCH_PLAYER1_ID} = p1.{USER_ID} '
            f'JOIN {USERS_TABLE} p2 ON m.{MATCH_PLAYER2_ID} = p2.{USER_ID} '
            f'WHERE p1.{USER_USERNAME} ILIKE %s OR p2.{USER_USERNAME} ILIKE %s '
            f'ORDER BY m.{MATCH_DATE} DESC',
            (f'%{search_term}%', f'%{search_term}%'),
        )
    else:
        cur.execute(
            f'SELECT m.*, p1.{USER_USERNAME}, p2.{USER_USERNAME} '
            f'FROM {MATCHES_TABLE} m '
            f'JOIN {USERS_TABLE} p1 ON m.{MATCH_PLAYER1_ID} = p1.{USER_ID} '
            f'JOIN {USERS_TABLE} p2 ON m.{MATCH_PLAYER2_ID} = p2.{USER_ID} '
            f'ORDER BY m.{MATCH_DATE} DESC'
        )
    matches = cur.fetchall()
    return render_template(
        'admin_matches.html', matches=matches, search_term=search_term
    )

@bp.route(f'/delete_match/<string:match_id>')
def admin_delete_match(match_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'DELETE FROM {MATCHES_TABLE} WHERE {MATCH_ID} = %s', (match_id,))
        conn.commit()
        flash('Match deleted successfully.', 'success')
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
    return redirect(url_for('.admin_matches'))

@bp.route('/friend_graph_data')
def friend_graph_data():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(f"SELECT {USER_ID}, {USER_USERNAME} FROM {USERS_TABLE}")
    users = cur.fetchall()
    cur.execute(
        f"SELECT {FRIENDS_USER_ID}, {FRIENDS_FRIEND_ID} FROM {FRIENDS_TABLE} WHERE {FRIENDS_STATUS} = 'accepted'"
    )
    friends = cur.fetchall()

    nodes = [{"id": str(user[USER_ID]), "label": user[USER_USERNAME]} for user in users]
    edges = [
        {"from": str(friend[FRIENDS_USER_ID]), "to": str(friend[FRIENDS_FRIEND_ID])}
        for friend in friends
    ]

    return jsonify({"nodes": nodes, "edges": edges})

@bp.route('/reset_db')
def reset_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f'TRUNCATE TABLE {FRIENDS_TABLE}, {USERS_TABLE}, {MATCHES_TABLE} CASCADE')
    conn.commit()
    return redirect(url_for('.admin'))

@bp.route('/reset-admin', methods=['GET', 'POST'])
def reset_admin():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Reset all users to not be admin
        cur.execute(f"UPDATE {USERS_TABLE} SET {USER_IS_ADMIN} = FALSE")
        # Set the first user to be admin
        cur.execute(
            f"UPDATE {USERS_TABLE} SET {USER_IS_ADMIN} = TRUE WHERE {USER_ID} = "
            f"(SELECT {USER_ID} FROM {USERS_TABLE} ORDER BY {USER_ID} LIMIT 1)"
        )
        conn.commit()
        return redirect(url_for('.admin'))

    return render_template('reset_admin.html')

@bp.route(f'/delete_user/<uuid:{USER_ID}>')
def delete_user(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f'DELETE FROM {FRIENDS_TABLE} WHERE {FRIENDS_USER_ID} = %s OR {FRIENDS_FRIEND_ID} = %s',
            (user_id, user_id),
        )
        cur.execute(f'DELETE FROM {USERS_TABLE} WHERE {USER_ID} = %s', (user_id,))
        conn.commit()
        flash('User deleted successfully.', 'success')
    except errors.ForeignKeyViolation as e:
        flash(f"Cannot delete user: {e}", 'danger')
        return render_template('error.html', error=f"Cannot delete user: {e}"), 500
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
        return render_template('error.html', error=str(e)), 500
    return redirect(url_for('user.users'))

@bp.route(f'/promote_user/<uuid:{USER_ID}>')
def promote_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f'UPDATE {USERS_TABLE} SET {USER_IS_ADMIN} = TRUE WHERE {USER_ID} = %s', (user_id,))
    conn.commit()
    return redirect(url_for('user.users'))

@bp.route(f'/reset_password/<uuid:{USER_ID}>')
def admin_reset_password(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'SELECT {USER_EMAIL} FROM {USERS_TABLE} WHERE {USER_ID} = %s', (user_id,))
        email = cur.fetchone()[0]
        new_password = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cur.execute(
            f'UPDATE {USERS_TABLE} SET {USER_PASSWORD} = %s WHERE {USER_ID} = %s',
            (hashed_password, user_id),
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
    cur.execute(f'SELECT {USER_USERNAME} FROM {USERS_TABLE}')
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
            f'INSERT INTO {USERS_TABLE} ('
            f'{USER_USERNAME}, {USER_PASSWORD}, {USER_EMAIL}, {USER_NAME}, '
            f'{USER_DUPR_RATING}, {USER_IS_ADMIN}) '
            'VALUES (%s, %s, %s, %s, %s, %s) '
            f'RETURNING {USER_ID}, {USER_USERNAME}, {USER_EMAIL}, {USER_NAME}, '
            f'{USER_DUPR_RATING}',
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
                    f'INSERT INTO {FRIENDS_TABLE} ({FRIENDS_USER_ID}, {FRIENDS_FRIEND_ID}, {FRIENDS_STATUS}) VALUES (%s, %s, %s)',
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
        cur.execute(
            f"SELECT {FRIENDS_USER_ID}, {FRIENDS_FRIEND_ID} FROM {FRIENDS_TABLE} WHERE {FRIENDS_STATUS} = 'accepted'"
        )
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
                f'INSERT INTO {MATCHES_TABLE} ('
                f'{MATCH_ID}, {MATCH_PLAYER1_ID}, {MATCH_PLAYER2_ID}, '
                f'{MATCH_PLAYER1_SCORE}, {MATCH_PLAYER2_SCORE}, {MATCH_DATE}) '
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
