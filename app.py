from flask import Flask, render_template, request, redirect, url_for, session
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from database import get_db_connection
from faker import Faker

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

mail = Mail(app)

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT to_regclass('public.users')")
    table_exists = cur.fetchone()[0]
    if not table_exists:
        return redirect(url_for('install'))
    cur.execute('SELECT id FROM users WHERE is_admin = TRUE')
    admin_exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    if not admin_exists:
        return redirect(url_for('install'))
    return redirect(url_for('login'))

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
        cur.execute('SELECT id FROM users WHERE is_admin = TRUE')
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
        try:
            dupr_rating = float(request.form['dupr_rating']) if request.form['dupr_rating'] else None
        except ValueError:
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id',
                        (username, hashed_password, email, name, dupr_rating, True))
            user_id = cur.fetchone()[0]
            conn.commit()
            session['user_id'] = user_id
            session['is_admin'] = True
        except:
            conn.rollback()
            return "Username already exists."
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('dashboard'))
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
            return render_template('login.html', error='Invalid username or password.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        try:
            dupr_rating = float(request.form['dupr_rating']) if request.form['dupr_rating'] else None
        except ValueError:
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE username = %s', (username,))
        existing_user = cur.fetchone()
        if existing_user:
            error = 'Username already exists. Please choose a different one.'
            cur.close()
            conn.close()
            return render_template('register.html', error=error)
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin, profile_picture) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                        (username, hashed_password, email, name, dupr_rating, False, 'pickaladder_icon.png'))
            conn.commit()
            msg = Message('Verify your email', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = 'Click the link to verify your email: {}'.format(url_for('verify_email', email=email, _external=True))
            mail.send(msg)
        except:
            conn.rollback()
            return "An error occurred during registration."
        finally:
            cur.close()
            conn.close()
        return redirect(url_for('login'))
    return render_template('register.html', error=error)

@app.context_processor
def inject_user():
    if 'user_id' in session:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id = %s', (session['user_id'],))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return dict(user=user)
    return dict(user=None)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT u.id, u.username, u.name, u.dupr_rating, u.profile_picture FROM users u JOIN friends f ON u.id = f.friend_id WHERE f.user_id = %s AND f.status = 'accepted'", (user_id,))
    friends = cur.fetchall()
    cur.execute('SELECT m.*, p1.username, p2.username FROM matches m JOIN users p1 ON m.player1_id = p1.id JOIN users p2 ON m.player2_id = p2.id WHERE m.player1_id = %s OR m.player2_id = %s ORDER BY m.match_date DESC', (user_id, user_id))
    matches = cur.fetchall()
    cur.execute("SELECT u.id, u.username FROM users u JOIN friends f ON u.id = f.user_id WHERE f.friend_id = %s AND f.status = 'pending'", (user_id,))
    requests = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', friends=friends, matches=matches, requests=requests)

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

    cur.execute("SELECT friend_id FROM friends WHERE user_id = %s AND status = 'accepted'", (user_id,))
    friends = [row[0] for row in cur.fetchall()]
    if friends:
        cur.execute(f"""
            SELECT DISTINCT u.id, u.username, u.name, u.dupr_rating
            FROM users u
            JOIN friends f1 ON u.id = f1.friend_id
            WHERE f1.user_id IN %s AND u.id != %s AND u.id NOT IN (SELECT friend_id FROM friends WHERE user_id = %s)
        """, (tuple(friends), user_id, user_id))
        fof = cur.fetchall()
    else:
        fof = []

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
        # Check if the friendship already exists
        cur.execute('SELECT * FROM friends WHERE (user_id = %s AND friend_id = %s) OR (user_id = %s AND friend_id = %s)', (user_id, friend_id, friend_id, user_id))
        if cur.fetchone() is None:
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
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
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

@app.route('/admin/reset-admin', methods=['GET', 'POST'])
def reset_admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        # Reset all users to not be admin
        cur.execute("UPDATE users SET is_admin = FALSE")
        # Set the first user to be admin
        cur.execute("UPDATE users SET is_admin = TRUE WHERE id = (SELECT id FROM users ORDER BY id LIMIT 1)")
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('admin'))

    cur.close()
    conn.close()
    return render_template('reset_admin.html')

@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('users'))

@app.route('/admin/promote_user/<int:user_id>')
def promote_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET is_admin = TRUE WHERE id = %s', (user_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('users'))

@app.route('/admin/generate_users')
def generate_users():
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
        dupr_rating = round(fake.pyfloat(left_digits=1, right_digits=2, positive=True, min_value=1.0, max_value=5.0), 2)
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, username, email, name, dupr_rating',
                    (username, hashed_password, email, name, dupr_rating, False))
        new_user = cur.fetchone()
        new_users.append(new_user)
    conn.commit()
    cur.close()
    conn.close()
    return render_template('generated_users.html', users=new_users)

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        msg = Message('Password reset', sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = 'Click the link to reset your password: {}'.format(url_for('reset_password', email=email, _external=True))
        mail.send(msg)
        return "Password reset email sent."
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

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password and password == confirm_password:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('UPDATE users SET password = %s WHERE id = %s', (hashed_password, user_id))
            conn.commit()
            cur.close()
            conn.close()
            return redirect(url_for('dashboard'))
        else:
            return render_template('change_password.html', user=user, error='Passwords do not match.')
    return render_template('change_password.html', user=user)

from utils import allowed_file

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    dark_mode = 'dark_mode' in request.form
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET dark_mode = %s WHERE id = %s', (dark_mode, user_id))
    conn.commit()
    cur.close()
    conn.close()
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    try:
        dupr_rating = float(request.form['dupr_rating']) if request.form['dupr_rating'] else None
    except ValueError:
        return "Invalid DUPR rating."
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

    cur.execute('UPDATE users SET dupr_rating = %s WHERE id = %s', (dupr_rating, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/create_match', methods=['GET', 'POST'])
def create_match():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        player1_id = user_id
        player2_id = request.form['player2']
        player1_score = request.form['player1_score']
        player2_score = request.form['player2_score']
        match_date = request.form['match_date']
        cur.execute('INSERT INTO matches (player1_id, player2_id, player1_score, player2_score, match_date) VALUES (%s, %s, %s, %s, %s)',
                    (player1_id, player2_id, player1_score, player2_score, match_date))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('dashboard'))
    cur.execute('SELECT u.id, u.username, u.name, u.dupr_rating, u.profile_picture FROM users u JOIN friends f ON u.id = f.friend_id WHERE f.user_id = %s', (user_id,))
    friends = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('create_match.html', friends=friends)

@app.route('/match/<int:match_id>')
def view_match(match_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT m.*, p1.username, p2.username FROM matches m JOIN users p1 ON m.player1_id = p1.id JOIN users p2 ON m.player2_id = p2.id WHERE m.id = %s', (match_id,))
    match = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('view_match.html', match=match)

@app.route('/friend_requests')
def friend_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT u.id, u.username FROM users u JOIN friends f ON u.id = f.user_id WHERE f.friend_id = %s AND f.status = 'pending'", (user_id,))
    requests = cur.fetchall()
    cur.execute("SELECT u.id, u.username, f.status FROM users u JOIN friends f ON u.id = f.friend_id WHERE f.user_id = %s", (user_id,))
    sent_requests = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('friend_requests.html', requests=requests, sent_requests=sent_requests)

@app.route('/accept_friend_request/<int:friend_id>')
def accept_friend_request(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE friends SET status = 'accepted' WHERE user_id = %s AND friend_id = %s", (friend_id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('friend_requests'))

@app.route('/decline_friend_request/<int:friend_id>')
def decline_friend_request(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM friends WHERE user_id = %s AND friend_id = %s", (friend_id, user_id))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('friend_requests'))

@app.route('/verify_email/<email>')
def verify_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = TRUE WHERE email = %s", (email,))
    conn.commit()
    cur.close()
    conn.close()
    return "Email verified."

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=27272)
