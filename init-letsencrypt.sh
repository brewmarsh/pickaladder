#!/bin/bash
set -e

# This script is designed to be run by the CI/CD pipeline on the production server.
# It handles the initial Let's Encrypt certificate generation automatically.

DOMAIN="pickaladder.io"
EMAIL="pickaladder@gmail.com"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

echo ">>> Checking for existing certificate at $CERT_DIR..."

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

    # 2. Start the web and nginx services. Nginx needs the web service to be
    # running to resolve the upstream, and it needs to be running itself
    # to solve the HTTP-01 challenge from Let's Encrypt.
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
docker-compose -f docker-compose.prod.yml up --build -d

echo ">>> Deployment script finished successfully."
