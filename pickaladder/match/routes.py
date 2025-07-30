from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from db import get_db_connection
from . import bp
import psycopg2
import uuid

@bp.route('/<uuid:match_id>')
def view_match_page(match_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        'SELECT m.*, p1.username, p2.username, p1.profile_picture, p2.profile_picture '
        'FROM matches m JOIN users p1 ON m.player1_id = p1.id '
        'JOIN users p2 ON m.player2_id = p2.id WHERE m.id = %s',
        (match_id,),
    )
    match = cur.fetchone()
    return render_template('view_match.html', match=match)


@bp.route('/create', methods=['GET', 'POST'])
def create_match():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        player1_id = user_id
        player2_id = request.form['player2']
        player1_score = request.form['player1_score']
        player2_score = request.form['player2_score']
        match_date = request.form['match_date']
        try:
            match_id = str(uuid.uuid4())
            cur.execute(
                'INSERT INTO matches (id, player1_id, player2_id, player1_score, player2_score, match_date) '
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
        'SELECT u.id, u.username, u.name, u.dupr_rating, u.profile_picture '
        'FROM users u JOIN friends f ON u.id = f.friend_id WHERE f.user_id = %s',
        (user_id,),
    )
    friends = cur.fetchall()
    return render_template('create_match.html', friends=friends)


@bp.route('/leaderboard')
def leaderboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # Calculate average scores and games played for each user
        cur.execute(
            """
            SELECT
                u.id,
                u.name,
                AVG(CASE WHEN m.player1_id = u.id THEN m.player1_score ELSE m.player2_score END) as avg_score,
                COUNT(m.id) as games_played
            FROM
                users u
            JOIN
                matches m ON u.id = m.player1_id OR u.id = m.player2_id
            GROUP BY
                u.id, u.name
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
