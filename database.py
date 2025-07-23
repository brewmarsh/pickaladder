import psycopg2
import os
import time

def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=os.environ.get("DB_HOST", "db"),
                database=os.environ['POSTGRES_DB'],
                user=os.environ['POSTGRES_USER'],
                password=os.environ['POSTGRES_PASSWORD'])
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            time.sleep(1)
    raise Exception("Could not connect to database")
