import psycopg2.pool
import os
from flask import g

pool = None

def init_pool():
    global pool
    pool = psycopg2.pool.SimpleConnectionPool(
        1,  # minconn
        20, # maxconn
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD']
    )

def get_db_connection():
    if 'db_conn' not in g:
        g.db_conn = pool.getconn()
    return g.db_conn

def close_db_connection(e=None):
    db_conn = g.pop('db_conn', None)
    if db_conn is not None:
        pool.putconn(db_conn)

def init_app(app):
    init_pool()
    app.teardown_appcontext(close_db_connection)
