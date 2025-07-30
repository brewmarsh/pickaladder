from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from pickaladder.db import get_db_connection
from . import bp
import psycopg2
import uuid
from pickaladder.constants import (
    USERS_TABLE,
    FRIENDS_TABLE,
    MATCHES_TABLE,
    USER_ID,
    USER_USERNAME,
    USER_NAME,
    USER_DUPR_RATING,
    USER_PROFILE_PICTURE,
    FRIENDS_USER_ID,
    FRIENDS_FRIEND_ID,
    MATCH_ID,
    MATCH_PLAYER1_ID,
    MATCH_PLAYER2_ID,
    MATCH_PLAYER1_SCORE,
    MATCH_PLAYER2_SCORE,
    MATCH_DATE,
)

@bp.route('/<uuid:match_id>')
def view_match_page(match_id):
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f'SELECT m.*, p1.{USER_USERNAME}, p2.{USER_USERNAME}, p1.{USER_PROFILE_PICTURE}, p2.{USER_PROFILE_PICTURE} '
        f'FROM {MATCHES_TABLE} m JOIN {USERS_TABLE} p1 ON m.{MATCH_PLAYER1_ID} = p1.{USER_ID} '
        f'JOIN {USERS_TABLE} p2 ON m.{MATCH_PLAYER2_ID} = p2.{USER_ID} WHERE m.{MATCH_ID} = %s',
        (match_id,),
    )
    match = cur.fetchone()
    return render_template('view_match.html', match=match)


@bp.route('/create', methods=['GET', 'POST'])
def create_match():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        player1_id = user_id
        player2_id = request.form['player2']
        player1_score = request.form[MATCH_PLAYER1_SCORE]
        player2_score = request.form[MATCH_PLAYER2_SCORE]
        match_date = request.form[MATCH_DATE]
        try:
            match_id = str(uuid.uuid4())
            cur.execute(
                f'INSERT INTO {MATCHES_TABLE} ({MATCH_ID}, {MATCH_PLAYER1_ID}, {MATCH_PLAYER2_ID}, {MATCH_PLAYER1_SCORE}, {MATCH_PLAYER2_SCORE}, {MATCH_DATE}) '
                'VALUES (%s, %s, %s, %s, %s, %s)',
                (
                    match_id,
                    player1_id,
                    player2_id,
                    player1_score,
                    player2_score,
                    match_date,
                ),
            )
            conn.commit()
            flash('Match created successfully.', 'success')
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred while creating the match: {e}", 'danger')
        return redirect(url_for('user.dashboard'))
    cur.execute(
        f'SELECT u.{USER_ID}, u.{USER_USERNAME}, u.{USER_NAME}, u.{USER_DUPR_RATING}, u.{USER_PROFILE_PICTURE} '
        f'FROM {USERS_TABLE} u JOIN {FRIENDS_TABLE} f ON u.{USER_ID} = f.{FRIENDS_FRIEND_ID} WHERE f.{FRIENDS_USER_ID} = %s',
        (user_id,),
    )
    friends = cur.fetchall()
    return render_template('create_match.html', friends=friends)


@bp.route('/leaderboard')
def leaderboard():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Calculate average scores and games played for each user
        cur.execute(
            f"""
            SELECT
                u.{USER_ID},
                u.{USER_NAME},
                AVG(CASE WHEN m.{MATCH_PLAYER1_ID} = u.{USER_ID} THEN m.{MATCH_PLAYER1_SCORE} ELSE m.{MATCH_PLAYER2_SCORE} END) as avg_score,
                COUNT(m.{MATCH_ID}) as games_played
            FROM
                {USERS_TABLE} u
            JOIN
                {MATCHES_TABLE} m ON u.{USER_ID} = m.{MATCH_PLAYER1_ID} OR u.{USER_ID} = m.{MATCH_PLAYER2_ID}
            GROUP BY
                u.{USER_ID}, u.{USER_NAME}
            ORDER BY
                avg_score DESC
            LIMIT 10
        """
        )
        players = cur.fetchall()
    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", 'danger')

    return render_template('leaderboard.html', players=players)
