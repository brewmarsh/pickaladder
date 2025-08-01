from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    g,
    current_app,
)
from pickaladder.db import get_db_connection
from . import bp
import psycopg2
import psycopg2.extras
from utils import allowed_file
from PIL import Image
import io
from pickaladder.constants import (
    USERS_TABLE,
    FRIENDS_TABLE,
    USER_ID,
    USER_USERNAME,
    USER_NAME,
    USER_DUPR_RATING,
    USER_PROFILE_PICTURE,
    USER_PROFILE_PICTURE_THUMBNAIL,
    USER_DARK_MODE,
    FRIENDS_USER_ID,
    FRIENDS_FRIEND_ID,
    FRIENDS_STATUS,
    MATCHES_TABLE,
    MATCH_PLAYER1_ID,
    MATCH_PLAYER2_ID,
    MATCH_DATE,
)

@bp.route('/dashboard')
def dashboard():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME}, u.{USER_NAME}, "
        f"u.{USER_DUPR_RATING}, u.{USER_PROFILE_PICTURE_THUMBNAIL} "
        f"FROM {USERS_TABLE} u JOIN {FRIENDS_TABLE} f "
        f"ON u.{USER_ID} = f.{FRIENDS_FRIEND_ID} "
        f"WHERE f.{FRIENDS_USER_ID} = %s AND f.{FRIENDS_STATUS} = 'accepted'",
        (user_id,),
    )
    friends = cur.fetchall()
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME} FROM {USERS_TABLE} u "
        f"JOIN {FRIENDS_TABLE} f ON u.{USER_ID} = f.{FRIENDS_USER_ID} "
        f"WHERE f.{FRIENDS_FRIEND_ID} = %s AND f.{FRIENDS_STATUS} = 'pending'",
        (user_id,),
    )
    requests = cur.fetchall()
    cur.execute(f'SELECT * FROM {USERS_TABLE} WHERE {USER_ID} = %s', (user_id,))
    user = cur.fetchone()
    return render_template(
        'user_dashboard.html', friends=friends, requests=requests, user=user
    )

@bp.route('/<uuid:user_id>')
def view_user(user_id):
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    current_app.logger.info(f"Viewing user profile for user_id: {user_id}")
    cur.execute(f'SELECT * FROM {USERS_TABLE} WHERE {USER_ID} = %s', (user_id,))
    user = cur.fetchone()
    current_app.logger.info(f"User object: {user}")

    if user is None:
        current_app.logger.info(f"User with user_id {user_id} not found.")
        return render_template('404.html'), 404

    # Get friends
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME}, u.{USER_NAME}, "
        f"u.{USER_DUPR_RATING}, u.{USER_PROFILE_PICTURE_THUMBNAIL} "
        f"FROM {USERS_TABLE} u JOIN {FRIENDS_TABLE} f "
        f"ON u.{USER_ID} = f.{FRIENDS_FRIEND_ID} "
        f"WHERE f.{FRIENDS_USER_ID} = %s AND f.{FRIENDS_STATUS} = 'accepted'",
        (user_id,),
    )
    friends = cur.fetchall()

    # Get match history
    cur.execute(
        f"SELECT m.*, p1.{USER_USERNAME} as player1, "
        f"p2.{USER_USERNAME} as player2 "
        f"FROM {MATCHES_TABLE} m "
        f"JOIN {USERS_TABLE} p1 ON m.{MATCH_PLAYER1_ID} = p1.{USER_ID} "
        f"JOIN {USERS_TABLE} p2 ON m.{MATCH_PLAYER2_ID} = p2.{USER_ID} "
        f"WHERE m.{MATCH_PLAYER1_ID} = %s OR m.{MATCH_PLAYER2_ID} = %s "
        f"ORDER BY m.{MATCH_DATE} DESC",
        (user_id, user_id),
    )
    matches = cur.fetchall()

    return render_template('user_profile.html', user=user, friends=friends, matches=matches)


@bp.route(f'/{USERS_TABLE}')
def users():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    search_term = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    if search_term:
        cur.execute(
            f'SELECT * FROM {USERS_TABLE} WHERE {USER_ID} != %s AND ({USER_USERNAME} ILIKE %s OR {USER_NAME} ILIKE %s)',
            (user_id, f'%{search_term}%', f'%{search_term}%'),
        )
    else:
        cur.execute(f'SELECT * FROM {USERS_TABLE} WHERE {USER_ID} != %s', (user_id,))
    all_users = cur.fetchall()

    cur.execute(
        f"SELECT {FRIENDS_FRIEND_ID} FROM {FRIENDS_TABLE} WHERE {FRIENDS_USER_ID} = %s AND {FRIENDS_STATUS} = 'accepted'",
        (user_id,),
    )
    friends = [row[0] for row in cur.fetchall()]
    if friends:
        cur.execute(
            f"""
            SELECT DISTINCT u.{USER_ID}, u.{USER_USERNAME}, u.{USER_NAME},
            u.{USER_DUPR_RATING}
            FROM {USERS_TABLE} u
            JOIN {FRIENDS_TABLE} f1 ON u.{USER_ID} = f1.{FRIENDS_FRIEND_ID}
            WHERE f1.{FRIENDS_USER_ID} IN %s AND u.{USER_ID} != %s
            AND u.{USER_ID} NOT IN (SELECT {FRIENDS_FRIEND_ID}
            FROM {FRIENDS_TABLE} WHERE {FRIENDS_USER_ID} = %s)
            """,
            (tuple(friends), user_id, user_id),
        )
        fof = cur.fetchall()
    else:
        fof = []

    return render_template(
        'users.html', all_users=all_users, search_term=search_term, fof=fof
    )


@bp.route('/add_friend/<string:friend_id>')
def add_friend(friend_id):
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    if user_id == friend_id:
        flash("You cannot add yourself as a friend.", 'danger')
        return redirect(request.referrer or url_for('.users'))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f'INSERT INTO {FRIENDS_TABLE} ({FRIENDS_USER_ID}, {FRIENDS_FRIEND_ID}) VALUES (%s, %s)',
            (user_id, friend_id),
        )
        conn.commit()
        flash('Friend request sent.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred while sending the friend request: {e}", 'danger')
    return redirect(request.referrer or url_for('.users'))


@bp.route(f'/{FRIENDS_TABLE}')
def friends():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME}, u.{USER_NAME}, "
        f"u.{USER_DUPR_RATING}, u.{USER_PROFILE_PICTURE} "
        f"FROM {USERS_TABLE} u JOIN {FRIENDS_TABLE} f "
        f"ON u.{USER_ID} = f.{FRIENDS_FRIEND_ID} "
        f"WHERE f.{FRIENDS_USER_ID} = %s AND f.{FRIENDS_STATUS} = 'accepted'",
        (user_id,),
    )
    friends = cur.fetchall()
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME} FROM {USERS_TABLE} u "
        f"JOIN {FRIENDS_TABLE} f ON u.{USER_ID} = f.{FRIENDS_USER_ID} "
        f"WHERE f.{FRIENDS_FRIEND_ID} = %s AND f.{FRIENDS_STATUS} = 'pending'",
        (user_id,),
    )
    requests = cur.fetchall()
    cur.execute(
        f"SELECT u.{USER_ID}, u.{USER_USERNAME}, f.{FRIENDS_STATUS} "
        f"FROM {USERS_TABLE} u JOIN {FRIENDS_TABLE} f "
        f"ON u.{USER_ID} = f.{FRIENDS_FRIEND_ID} "
        f"WHERE f.{FRIENDS_USER_ID} = %s AND f.{FRIENDS_STATUS} = 'pending'",
        (user_id,),
    )
    sent_requests = cur.fetchall()
    return render_template(
        'friends.html',
        friends=friends,
        requests=requests,
        sent_requests=sent_requests,
    )


@bp.route('/accept_friend_request/<string:friend_id>')
def accept_friend_request(friend_id):
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE {FRIENDS_TABLE} SET {FRIENDS_STATUS} = 'accepted' WHERE {FRIENDS_USER_ID} = %s AND {FRIENDS_FRIEND_ID} = %s",
            (friend_id, user_id),
        )
        cur.execute(
            f"INSERT INTO {FRIENDS_TABLE} ({FRIENDS_USER_ID}, {FRIENDS_FRIEND_ID}, {FRIENDS_STATUS}) VALUES (%s, %s, %s)",
            (user_id, friend_id, 'accepted'),
        )
        conn.commit()
        flash('Friend request accepted.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred while accepting the friend request: {e}", 'danger')
    return redirect(url_for('.friends'))


@bp.route('/decline_friend_request/<string:friend_id>')
def decline_friend_request(friend_id):
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"DELETE FROM {FRIENDS_TABLE} WHERE {FRIENDS_USER_ID} = %s AND {FRIENDS_FRIEND_ID} = %s",
        (friend_id, user_id),
    )
    conn.commit()
    return redirect(url_for('.friends'))


@bp.route(f'/{USER_PROFILE_PICTURE}/<string:user_id>')
def profile_picture(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'SELECT {USER_PROFILE_PICTURE} FROM {USERS_TABLE} WHERE id = %s', (user_id,))
        profile_picture_data = cur.fetchone()
        if profile_picture_data and profile_picture_data[0]:
            return Response(profile_picture_data[0], mimetype='image/png')
        else:
            return redirect(url_for('static', filename='user_icon.png'))
    except Exception as e:
        current_app.logger.error(f"Error serving profile picture: {e}")
        return redirect(url_for('static', filename='user_icon.png'))


@bp.route(f'/{USER_PROFILE_PICTURE_THUMBNAIL}/<string:user_id>')
def profile_picture_thumbnail(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f'SELECT {USER_PROFILE_PICTURE_THUMBNAIL} FROM {USERS_TABLE} WHERE {USER_ID} = %s',
            (user_id,),
        )
        thumbnail_data = cur.fetchone()
        if thumbnail_data and thumbnail_data[0]:
            return Response(thumbnail_data[0], mimetype='image/png')
        else:
            return redirect(url_for('static', filename='user_icon.png'))
    except Exception as e:
        current_app.logger.error(f"Error serving profile picture thumbnail: {e}")
        return redirect(url_for('static', filename='user_icon.png'))


@bp.route('/update_profile', methods=['POST'])
def update_profile():
    if USER_ID not in session:
        return redirect(url_for('auth.login'))
    user_id = session[USER_ID]
    try:
        dark_mode = USER_DARK_MODE in request.form
        dupr_rating = (
            float(request.form.get(USER_DUPR_RATING))
            if request.form.get(USER_DUPR_RATING)
            else None
        )
        profile_picture = request.files.get(USER_PROFILE_PICTURE)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            f'UPDATE {USERS_TABLE} SET {USER_DARK_MODE} = %s WHERE {USER_ID} = %s',
            (dark_mode, user_id),
        )

        if (
            profile_picture
            and profile_picture.filename
            and allowed_file(profile_picture.filename)
        ):
            if len(profile_picture.read()) > 10 * 1024 * 1024:
                flash('Profile picture is too large. The maximum size is 10MB.', 'danger')
                return redirect(request.referrer or url_for('.dashboard'))
            profile_picture.seek(0)
            img = Image.open(profile_picture)
            img.thumbnail((512, 512))

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            profile_picture_data = buf.getvalue()

            img.thumbnail((64, 64))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            thumbnail_data = buf.getvalue()

            cur.execute(
                f'UPDATE {USERS_TABLE} SET {USER_PROFILE_PICTURE} = %s, '
                f'{USER_PROFILE_PICTURE_THUMBNAIL} = %s '
                f'WHERE {USER_ID} = %s',
                (profile_picture_data, thumbnail_data, user_id),
            )
            current_app.logger.info(
                f"User {user_id} updated their profile picture."
            )
        elif profile_picture:
            flash('Invalid file type for profile picture.', 'danger')
            return redirect(request.referrer or url_for('.dashboard'))

        if dupr_rating is not None:
            cur.execute(
                f'UPDATE {USERS_TABLE} SET {USER_DUPR_RATING} = %s WHERE {USER_ID} = %s',
                (dupr_rating, user_id),
            )

        conn.commit()
    except psycopg2.errors.UndefinedColumn as e:
        flash(
            (
                f"Database error: {e}. The 'dark_mode' column is missing. "
                "Please run database migrations or contact an administrator."
            ),
            'danger',
        )
        return render_template('error.html', error=str(e)), 500
    except psycopg2.Error as e:
        flash(f"Database error: {e}", 'danger')
        return render_template('error.html', error=str(e)), 500
    except Exception as e:
        flash(f"An error occurred: {e}", 'danger')
        return render_template('error.html', error=str(e)), 500
    return redirect(url_for('.dashboard'))
