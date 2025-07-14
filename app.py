from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash

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
    return render_template('index.html')

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
        dupr_rating = request.form['dupr_rating']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT id FROM users')
        is_first_user = cur.fetchone() is None
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating, is_admin) VALUES (%s, %s, %s, %s, %s, %s)',
                        (username, hashed_password, email, name, dupr_rating, is_first_user))
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
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id != %s', (user_id,))
    all_users = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('users.html', all_users=all_users)

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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=27272)
