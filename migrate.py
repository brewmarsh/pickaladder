import os
from pickaladder import create_app, db
from sqlalchemy import text
from pickaladder.constants import (
    MIGRATIONS_TABLE,
    MIGRATION_NAME,
)


def apply_migrations():
    """
    Connects to the database via SQLAlchemy and applies any pending raw SQL migrations
    from the 'migrations' directory.
    """
    app = create_app()
    with app.app_context():
        migration_dir = "migrations"
        print("Running database migrations...")

        if not os.path.exists(migration_dir):
            print("No 'migrations' directory found. Skipping.")
            return

        with db.engine.connect() as connection:
            # Begin a transaction
            trans = connection.begin()
            try:
                # Ensure the migrations table exists.
                # NOTE: The following queries are safe from SQL injection because the
                # table and column names are defined as constants in the codebase,
                # not from user input.
                query = (
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name = %s"
                )
                result = connection.execute(text(query), (MIGRATIONS_TABLE,))
                if result.fetchone() is None:
                    print(f"Creating '{MIGRATIONS_TABLE}' table.")
                    connection.execute(
                        text(
                            f"CREATE TABLE {MIGRATIONS_TABLE} ("
                            "id SERIAL PRIMARY KEY, "
                            f"{MIGRATION_NAME} TEXT NOT NULL UNIQUE)"
                        )
                    )

                # Get the set of already applied migrations.
                query = "SELECT %s FROM %s"
                result = connection.execute(
                    text(query), (MIGRATION_NAME, MIGRATIONS_TABLE)
                )
                applied_migrations = {row[0] for row in result.fetchall()}
                print(f"Found {len(applied_migrations)} applied migrations.")

                # Find and apply new migrations.
                migration_files = sorted(
                    [f for f in os.listdir(migration_dir) if f.endswith(".sql")]
                )
                for migration_file in migration_files:
                    if migration_file not in applied_migrations:
                        print(f"Applying migration: {migration_file}...")
                        with open(
                            os.path.join(migration_dir, migration_file), "r"
                        ) as f:
                            sql = f.read()
                            connection.execute(text(sql))

                        # Record the migration so it doesn't run again.
                        query = "INSERT INTO %s (%s) VALUES (:migration_file)"
                        connection.execute(
                            text(query),
                            (MIGRATIONS_TABLE, MIGRATION_NAME, migration_file),
                        )

                # Commit the transaction
                trans.commit()
                print("Successfully applied all new migrations.")

            except Exception as e:
                print(f"An error occurred during migrations: {e}")
                # Rollback the transaction in case of error
                trans.rollback()
                raise

        print("Database migrations complete.")


if __name__ == "__main__":
    apply_migrations()
