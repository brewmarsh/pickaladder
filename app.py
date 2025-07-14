from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

def get_db_connection():
    conn = psycopg2.connect(
        host="db",
        database=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'])
    return conn

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
        try:
            cur.execute('INSERT INTO users (username, password, email, name, dupr_rating) VALUES (%s, %s, %s, %s, %s)',
                        (username, hashed_password, email, name, dupr_rating))
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

if __name__ == '__main__':
    app.run(debug=True, host='0.a.a.a', port=27272)
