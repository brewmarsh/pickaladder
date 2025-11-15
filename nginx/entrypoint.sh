#!/bin/sh
set -e

# This script is the entrypoint for the Nginx container.
# It waits until the 'web' service is reachable before starting Nginx.

UPSTREAM_HOST="web"
UPSTREAM_PORT="27272"

echo ">>> Nginx Entrypoint: Waiting for upstream host $UPSTREAM_HOST..."

# Use a loop to check if the upstream host is resolvable.
# 'getent hosts' is a standard way to check for hostname resolution.
until getent hosts $UPSTREAM_HOST; do
    echo "Still waiting for upstream host $UPSTREAM_HOST..."
    sleep 2
done

echo ">>> Nginx Entrypoint: Upstream host found. Starting Nginx..."

# Execute the original Nginx entrypoint script.
# This will start the Nginx process.
exec /docker-entrypoint.sh nginx -g 'daemon off;'
