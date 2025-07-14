from flask import Flask
import psycopg2
import os

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(
        host="db",
        database=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'])
    return conn

@app.route('/')
def hello_world():
    try:
        conn = get_db_connection()
        conn.close()
        return 'Hello, World! Database connection successful.'
    except Exception as e:
        return f"Hello, World! Database connection failed: {e}"

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=27272)
