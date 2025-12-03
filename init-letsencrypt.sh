#!/bin/bash
set -e

# Cleanup legacy containers if they exist (to fix port conflicts during renaming)
echo ">>> Removing legacy containers to prevent conflicts..."

# 1. Try to take down the project gracefully
# We ignore errors here because the state might be corrupted (hence the KeyError)
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

# 2. Force remove containers by label (matches any container in the project)
# This finds all containers belonging to 'picka-server' project
container_ids=$(docker ps -a --filter "label=com.docker.compose.project=picka-server" -q)
if [ -n "$container_ids" ]; then
    echo ">>> Removing containers by label: $container_ids"
    docker rm -f $container_ids || true
fi

# 3. Force remove by known names (legacy and new) just in case labels are missing
# or the project name was different in the past.
docker rm -f picka-server_nginx_1 picka-server_web_1 picka-server_certbot_1 \
             picka-web picka-nginx picka-certbot 2>/dev/null || true

# This script is designed to be run by the CI/CD pipeline on the production server.
# It handles the initial Let's Encrypt certificate generation automatically.

DOMAIN="pickaladder.io"
EMAIL="pickaladder@gmail.com"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

echo ">>> Checking for existing certificate at $CERT_DIR..."

# Check for dummy certificate or incomplete state
if [ -d "$CERT_DIR" ]; then
    if [ -f "$CERT_DIR/fullchain.pem" ]; then
        if sudo openssl x509 -in "$CERT_DIR/fullchain.pem" -text -noout | grep -q "CN.*=.*localhost"; then
            echo ">>> Detected dummy certificate. Removing to force regeneration..."
            sudo rm -rf "$CERT_DIR"
        fi
    else
        echo ">>> Certificate directory exists but fullchain.pem is missing. Removing..."
        sudo rm -rf "$CERT_DIR"
    fi
fi

# The main deployment logic is wrapped in this if/else block.
# If a certificate already exists, we just start the services.
# If not, we run the one-time generation process.
if [ -d "$CERT_DIR" ]; then
    echo "Certificate found. Starting services..."
else
    echo "Certificate not found. Starting first-time generation process..."

    # 1. Create dummy certificate files so Nginx can start
    echo ">>> Creating dummy certificate..."
    sudo mkdir -p $CERT_DIR
    sudo openssl req -x509 -nodes -newkey rsa:4096 -days 1 \
        -keyout "$CERT_DIR/privkey.pem" \
        -out "$CERT_DIR/fullchain.pem" \
        -subj "/CN=localhost"

    # 2. Start the web and nginx services. The new Nginx entrypoint will
    # automatically wait for the web service to be ready.
    echo ">>> Starting web and nginx with dummy certificate..."
    docker-compose -f docker-compose.prod.yml up -d web nginx

    # 3. Replace the dummy certificate with a real one from Let's Encrypt.
    # We remove the dummy files before certbot runs.
    echo ">>> Requesting real certificate from Let's Encrypt..."
    sudo rm -rf $CERT_DIR
    docker-compose -f docker-compose.prod.yml run --rm certbot certonly --webroot \
        --webroot-path /var/www/certbot \
        --email $EMAIL \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d $DOMAIN -d www.$DOMAIN

    # 4. Stop the Nginx container that was using the dummy cert.
    # The next step will bring everything up with the real cert.
    echo ">>> Shutting down Nginx..."
    docker-compose -f docker-compose.prod.yml down
fi

# 5. Start or restart all services with the final configuration and real certificate.
echo ">>> Starting all services for production..."
docker-compose -f docker-compose.prod.yml up --build -d --remove-orphans

echo ">>> Deployment script finished successfully."
