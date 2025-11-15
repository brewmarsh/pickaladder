#!/bin/sh
set -e

# This script is the entrypoint for the Nginx container.
# It waits until the upstream 'web' service is not only resolvable
# but also actively listening on its port before starting Nginx.

UPSTREAM_HOST="web"
UPSTREAM_PORT="27272"

echo ">>> Nginx Entrypoint: Waiting for upstream service $UPSTREAM_HOST:$UPSTREAM_PORT..."

# Use a loop with netcat (nc) to check if the port is open.
# This is a more reliable check than just resolving the hostname, as it
# ensures the application inside the 'web' container is actually running.
while ! nc -z $UPSTREAM_HOST $UPSTREAM_PORT; do
    echo "Still waiting for upstream service $UPSTREAM_HOST:$UPSTREAM_PORT..."
    sleep 2
done

echo ">>> Nginx Entrypoint: Upstream service is ready. Starting Nginx..."

# Execute the original Nginx entrypoint script to start the Nginx process.
exec /docker-entrypoint.sh nginx -g 'daemon off;'
