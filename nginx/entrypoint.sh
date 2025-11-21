#!/bin/sh
set -e

# Wait for the web service to be ready
echo "Waiting for web service..."
while ! nc -z web 27272; do
  sleep 0.1
done
echo "Web service is ready!"

exec "$@"
