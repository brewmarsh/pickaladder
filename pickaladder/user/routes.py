from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    g
)
from pickaladder.db import get_db_connection
from . import bp
import psycopg2
from utils import allowed_file
from PIL import Image
import io

@bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        "SELECT u.id, u.username, u.name, u.dupr_rating, u.profile_picture_thumbnail "
        "FROM users u JOIN friends f ON u.id = f.friend_id "
        "WHERE f.user_id = %s AND f.status = 'accepted'",
        (user_id,),
    )
    friends = cur.fetchall()
    cur.execute(
        "SELECT u.id, u.username FROM users u JOIN friends f ON u.id = f.user_id "
        "WHERE f.friend_id = %s AND f.status = 'pending'",
        (user_id,),
    )
    requests = cur.fetchall()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    return render_template(
        'user_dashboard.html', friends=friends, requests=requests, user=user
    )

@bp.route('/<string:user_id>')
def view_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    return render_template('user_profile.html', user=user)


@bp.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    search_term = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    if search_term:
        cur.execute(
            'SELECT * FROM users WHERE id != %s AND (username ILIKE %s OR name ILIKE %s)',
            (user_id, f'%{search_term}%', f'%{search_term}%'),
        )
    else:
        cur.execute('SELECT * FROM users WHERE id != %s', (user_id,))
    all_users = cur.fetchall()

    cur.execute(
        "SELECT friend_id FROM friends WHERE user_id = %s AND status = 'accepted'",
        (user_id,),
    )
    friends = [row[0] for row in cur.fetchall()]
    if friends:
        cur.execute(
            """
            SELECT DISTINCT u.id, u.username, u.name, u.dupr_rating
            FROM users u
            JOIN friends f1 ON u.id = f1.friend_id
            WHERE f1.user_id IN %s AND u.id != %s AND u.id NOT IN (SELECT friend_id FROM friends WHERE user_id = %s)
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    if user_id == friend_id:
        flash("You cannot add yourself as a friend.", 'danger')
        return redirect(request.referrer or url_for('.users'))
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO friends (user_id, friend_id) VALUES (%s, %s)',
            (user_id, friend_id),
        )
        conn.commit()
        flash('Friend request sent.', 'success')
    except Exception as e:
        conn.rollback()
        flash(f"An error occurred while sending the friend request: {e}", 'danger')
    return redirect(request.referrer or url_for('.users'))


@bp.route('/friends')
def friends():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT u.id, u.username, u.name, u.dupr_rating, u.profile_picture "
        "FROM users u JOIN friends f ON u.id = f.friend_id "
        "WHERE f.user_id = %s AND f.status = 'accepted'",
        (user_id,),
    )
    friends = cur.fetchall()
    cur.execute(
        "SELECT u.id, u.username FROM users u JOIN friends f ON u.id = f.user_id "
        "WHERE f.friend_id = %s AND f.status = 'pending'",
        (user_id,),
    )
    requests = cur.fetchall()
    cur.execute(
        "SELECT u.id, u.username, f.status FROM users u JOIN friends f ON u.id = f.friend_id "
        "WHERE f.user_id = %s AND f.status = 'pending'",
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE friends SET status = 'accepted' WHERE user_id = %s AND friend_id = %s",
            (friend_id, user_id),
        )
        cur.execute(
            "INSERT INTO friends (user_id, friend_id, status) VALUES (%s, %s, %s)",
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM friends WHERE user_id = %s AND friend_id = %s",
        (friend_id, user_id),
    )
    conn.commit()
    return redirect(url_for('.friends'))


@bp.route('/profile_picture/<string:user_id>')
def profile_picture(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT profile_picture FROM users WHERE id = %s', (user_id,))
        profile_picture_data = cur.fetchone()
        if profile_picture_data and profile_picture_data[0]:
            return Response(profile_picture_data[0], mimetype='image/png')
        else:
            return redirect(url_for('static', filename='user_icon.png'))
    except Exception as e:
        current_app.logger.error(f"Error serving profile picture: {e}")
        return redirect(url_for('static', filename='user_icon.png'))


@bp.route('/profile_picture_thumbnail/<string:user_id>')
def profile_picture_thumbnail(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT profile_picture_thumbnail FROM users WHERE id = %s', (user_id,))
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
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    try:
        dark_mode = 'dark_mode' in request.form
        dupr_rating = (
            float(request.form.get('dupr_rating'))
            if request.form.get('dupr_rating')
            else None
        )
        profile_picture = request.files.get('profile_picture')

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute('UPDATE users SET dark_mode = %s WHERE id = %s', (dark_mode, user_id))

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
                'UPDATE users SET profile_picture = %s, profile_picture_thumbnail = %s '
                'WHERE id = %s',
                (profile_picture_data, thumbnail_data, user_id),
            )
            current_app.logger.info(f"User {user_id} updated their profile picture.")
        elif profile_picture:
            flash('Invalid file type for profile picture.', 'danger')
            return redirect(request.referrer or url_for('.dashboard'))

        if dupr_rating is not None:
            cur.execute('UPDATE users SET dupr_rating = %s WHERE id = %s', (dupr_rating, user_id))

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
