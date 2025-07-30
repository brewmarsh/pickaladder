from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    current_app
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
import string
from PIL import Image, ImageDraw
from io import BytesIO

from db import get_db_connection
from . import bp
from pickaladder import mail
import psycopg2


@bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        try:
            dupr_rating = (
                float(request.form['dupr_rating'])
                if request.form['dupr_rating']
                else None
            )
        except ValueError:
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cur.fetchone()
        if existing_user:
            error = 'Username already exists. Please choose a different one.'
            return render_template('register.html', error=error)
        try:
            cur.execute(
                'INSERT INTO users (username, password, email, name, dupr_rating, is_admin) '
                'VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                (username, hashed_password, email, name, dupr_rating, False),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            session['user_id'] = str(user_id)
            session['is_admin'] = False
            current_app.logger.info(f"New user registered: {username}")

            # Generate profile picture
            img = Image.new('RGB', (256, 256), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            initials = "".join([name[0] for name in name.split()])
            d.text((128, 128), initials, fill=(255, 255, 0))
            import io

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
            conn.commit()
            msg = Message(
                'Verify your email',
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[email],
            )
            msg.body = (
                'Click the link to verify your email: {}'.format(
                    url_for('auth.verify_email', email=email, _external=True)
                )
            )
            mail.send(msg)
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('auth.register'))
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", 'danger')
            return "An error occurred during registration."
        return redirect(url_for('user.dashboard'))
    return render_template('register.html', error=error)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            session['user_id'] = str(user[0])
            session['is_admin'] = user[6]
            return redirect(url_for('user.dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@bp.route('/install', methods=['GET', 'POST'])
def install():
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if an admin user already exists.
    cur.execute('SELECT id FROM users WHERE is_admin = TRUE')
    admin_exists = cur.fetchone()
    if admin_exists:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        try:
            dupr_rating = (
                float(request.form['dupr_rating'])
                if request.form['dupr_rating']
                else None
            )
        except ValueError:
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cur.execute(
                'INSERT INTO users (username, password, email, name, dupr_rating, is_admin) '
                'VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                (username, hashed_password, email, name, dupr_rating, True),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            session['user_id'] = str(user_id)
            session['is_admin'] = True
            current_app.logger.info(f"New user registered: {username}")

            # Generate profile picture
            img = Image.new('RGB', (256, 256), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            initials = "".join([name[0] for name in name.split()])
            d.text((128, 128), initials, fill=(255, 255, 0))
            buf = BytesIO()
            img.save(buf, format='PNG')
            profile_picture_data = buf.getvalue()

            img.thumbnail((64, 64))
            buf = BytesIO()
            img.save(buf, format='PNG')
            thumbnail_data = buf.getvalue()

            cur.execute(
                'UPDATE users SET profile_picture = %s, profile_picture_thumbnail = %s '
                'WHERE id = %s',
                (profile_picture_data, thumbnail_data, user_id),
            )
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('auth.install'))
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", 'danger')
            return "An error occurred during installation."
        return redirect(url_for('user.dashboard'))
    return render_template('install.html')


@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        msg = Message(
            'Password reset', sender=current_app.config['MAIL_USERNAME'], recipients=[email]
        )
        msg.body = 'Click the link to reset your password: {}'.format(
            url_for('auth.reset_password', email=email, _external=True)
        )
        mail.send(msg)
        return "Password reset email sent."
    return render_template('forgot_password.html')


@bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email')
    if request.method == 'POST':
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'UPDATE users SET password = %s WHERE email = %s', (hashed_password, email)
        )
        conn.commit()
        return redirect(url_for('auth.login'))
    return render_template('reset_password.html', email=email)


@bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password and password == confirm_password:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            cur.execute(
                'UPDATE users SET password = %s WHERE id = %s', (hashed_password, user_id)
            )
            conn.commit()
            return redirect(url_for('user.dashboard'))
        else:
            return render_template(
                'change_password.html', user=user, error='Passwords do not match.'
            )
    return render_template('change_password.html', user=user)


@bp.route('/verify_email/<email>')
def verify_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET email_verified = TRUE WHERE email = %s", (email,))
    conn.commit()
    flash("Email verified. You can now log in.", "success")
    return redirect(url_for('auth.login'))
