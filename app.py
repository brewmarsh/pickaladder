from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)

import time

def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host="db",
                database=os.environ['POSTGRES_DB'],
                user=os.environ['POSTGRES_USER'],
                password=os.environ['POSTGRES_PASSWORD'])
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            time.sleep(1)
    raise Exception("Could not connect to database")

@app.route('/')
def index():
    return redirect(url_for('install'))

@app.route('/install', methods=['GET', 'POST'])
def install():
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if the users table exists
    cur.execute("SELECT to_regclass('public.users')")
    table_exists = cur.fetchone()[0]

    if not table_exists:
        # If the table does not exist, create it by executing init.sql
        with open('init.sql', 'r') as f:
            cur.execute(f.read())
        conn.commit()
    else:
        # If the table exists, check if there are any users
        cur.execute('SELECT id FROM users')
        user_exists = cur.fetchone() is not None
        if user_exists:
            cur.close()
            conn.close()
            return redirect(url_for('login'))

    if request.method == 'GET':
        # Now, we either have a fresh DB or an empty one, show the install form.
        return render_template('install.html')

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        dupr_rating = request.form['dupr_rating'] or None
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin) VALUES (%s, %s, %s, %s, %s, %s)',
                        (username, hashed_password, email, name, dupr_rating, True))
            conn.commit()
        except:
            conn.rollback()
            return "Username already exists."
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('login'))
    return render_template('install.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['is_admin'] = user[6]
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid username or password.'
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        dupr_rating = request.form['dupr_rating'] or None
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin) VALUES (%s, %s, %s, %s, %s, %s)',
                        (username, hashed_password, email, name, dupr_rating, False))
            conn.commit()
        except:
            conn.rollback()
            return "Username already exists."
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.execute('SELECT u.id, u.username, u.name, u.dupr_rating FROM users u JOIN friends f ON u.id = f.friend_id WHERE f.user_id = %s', (user_id,))
    friends = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', user=user, friends=friends)

@app.route('/users')
def users():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    search_term = request.args.get('search', '')
    conn = get_db_connection()
    cur = conn.cursor()
    if search_term:
        cur.execute('SELECT * FROM users WHERE id != %s AND (username ILIKE %s OR name ILIKE %s)', (user_id, f'%{search_term}%', f'%{search_term}%'))
    else:
        cur.execute('SELECT * FROM users WHERE id != %s', (user_id,))
    all_users = cur.fetchall()

    cur.execute("""
        SELECT DISTINCT u.id, u.username, u.name, u.dupr_rating
        FROM users u
        JOIN friends f1 ON u.id = f1.friend_id
        JOIN friends f2 ON f1.user_id = f2.friend_id
        WHERE f2.user_id = %s AND u.id != %s AND u.id NOT IN (SELECT friend_id FROM friends WHERE user_id = %s)
    """, (user_id, user_id, user_id))
    fof = cur.fetchall()

    cur.close()
    conn.close()
    return render_template('users.html', all_users=all_users, search_term=search_term, fof=fof)

@app.route('/add_friend/<int:friend_id>')
def add_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO friends (user_id, friend_id) VALUES (%s, %s)', (user_id, friend_id))
        conn.commit()
    except:
        conn.rollback()
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('users'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT is_admin FROM users WHERE id = %s', (user_id,))
    is_admin = cur.fetchone()[0]
    cur.close()
    conn.close()
    if not is_admin:
        return redirect(url_for('dashboard'))
    return render_template('admin.html')

@app.route('/admin/reset_db')
def reset_db():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT is_admin FROM users WHERE id = %s', (user_id,))
    is_admin = cur.fetchone()[0]
    if not is_admin:
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))

    cur.execute('TRUNCATE TABLE friends, users RESTART IDENTITY')
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        # In a real application, you would send an email with a password reset link.
        # For this example, we'll just redirect to a page where they can enter a new password.
        return redirect(url_for('reset_password', email=email))
    return render_template('forgot_password.html')

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    email = request.args.get('email')
    if request.method == 'POST':
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('UPDATE users SET password = %s WHERE email = %s', (hashed_password, email))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('login'))
    return render_template('reset_password.html', email=email)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    dupr_rating = request.form['dupr_rating'] or None
    password = request.form['password']
    profile_picture = request.files['profile_picture']
    conn = get_db_connection()
    cur = conn.cursor()

    if profile_picture and allowed_file(profile_picture.filename):
        filename = secure_filename(profile_picture.filename)
        upload_folder = 'static/uploads'
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        profile_picture.save(os.path.join(upload_folder, filename))
        cur.execute('UPDATE users SET profile_picture = %s WHERE id = %s', (filename, user_id))

    if password:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        cur.execute('UPDATE users SET dupr_rating = %s, password = %s WHERE id = %s', (dupr_rating, hashed_password, user_id))
    else:
        cur.execute('UPDATE users SET dupr_rating = %s WHERE id = %s', (dupr_rating, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=27272)
