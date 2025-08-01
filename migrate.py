import os
import psycopg2
from pickaladder import create_app
from pickaladder.db import get_db_connection
from pickaladder.constants import (
    MIGRATIONS_TABLE,
    MIGRATION_ID,
    MIGRATION_NAME,
)

def apply_migrations():
    """
    Connects to the database and applies any pending migrations from the 'migrations' directory.
    """
    app = create_app()
    with app.app_context():
        conn = get_db_connection()
        cur = conn.cursor()
        migration_dir = 'migrations'

        print("Running database migrations...")

        if not os.path.exists(migration_dir):
            print("No 'migrations' directory found. Skipping.")
            return

        # Ensure the migrations table exists to track applied migrations.
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema = 'public' "
            f"AND table_name = '{MIGRATIONS_TABLE}'"
        )
        if cur.fetchone() is None:
            print(f"Creating '{MIGRATIONS_TABLE}' table.")
            cur.execute(
                f'CREATE TABLE {MIGRATIONS_TABLE} ('
                f'{MIGRATION_ID} SERIAL PRIMARY KEY, '
                f'{MIGRATION_NAME} TEXT NOT NULL UNIQUE)'
            )
            conn.commit()

        # Get the set of already applied migrations.
        cur.execute(f'SELECT {MIGRATION_NAME} FROM {MIGRATIONS_TABLE}')
        applied_migrations = {row[0] for row in cur.fetchall()}
        print(f"Found {len(applied_migrations)} applied migrations.")

        # Find and apply new migrations.
        migration_files = sorted(
            [f for f in os.listdir(migration_dir) if f.endswith('.sql')]
        )
        for migration_file in migration_files:
            if migration_file not in applied_migrations:
                print(f"Applying migration: {migration_file}...")
                with open(os.path.join(migration_dir, migration_file), 'r') as f:
                    sql = f.read()
                    cur.execute(sql)

                # Record the migration so it doesn't run again.
                cur.execute(
                    f'INSERT INTO {MIGRATIONS_TABLE} ({MIGRATION_NAME}) VALUES (%s)',
                    (migration_file,),
                )
                conn.commit()
                print(f"Successfully applied {migration_file}.")

        print("Database migrations complete.")

if __name__ == '__main__':
    apply_migrations()
