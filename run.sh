#!/bin/bash

# Start a postgres container
docker run -d --name picka-db -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:13

# Wait for the database to be ready
echo "Waiting for database to start..."
sleep 10

# Run the application
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=password
export POSTGRES_DB=postgres
export DB_HOST=localhost
python3 app.py
