#!/bin/bash
set -e

# Check if the database already exists
if psql -lqt --username "$POSTGRES_USER" | cut -d \| -f 1 | grep -qw "$POSTGRES_DB"; then
  echo "Database $POSTGRES_DB already exists."
else
  # Create the database
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
      CREATE DATABASE "$POSTGRES_DB";
EOSQL
fi

# Add uuid-ossp extension to the template database so all new DBs have it
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "template1" -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'

# Run the schema on the main database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/init.sql
