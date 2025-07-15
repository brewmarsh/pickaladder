#!/bin/bash
set -e

# Start PostgreSQL in the background
docker-entrypoint.sh postgres &

# Wait for PostgreSQL to be ready
until pg_isready -h localhost -p 5432 -U "$POSTGRES_USER"; do
  echo "Waiting for postgres..."
  sleep 2
done

# Run the reset script
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DROP SCHEMA public CASCADE;
    CREATE SCHEMA public;
    \i /docker-entrypoint-initdb.d/init.sql
EOSQL

# Keep the container running
wait
