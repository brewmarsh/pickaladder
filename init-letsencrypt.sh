#!/bin/bash
set -e

# Cleanup legacy containers if they exist (to fix port conflicts during renaming)
echo ">>> Removing legacy containers to prevent conflicts..."

# Stop conflicting host services (nginx/apache) that might bind to port 80/443
echo ">>> Stopping conflicting host web services..."
sudo systemctl stop nginx 2>/dev/null || true
sudo systemctl stop apache2 2>/dev/null || true
sudo systemctl stop httpd 2>/dev/null || true

# Aggressively cleanup any process or container holding port 80/443
echo ">>> checking for port conflicts on 80 and 443..."
# 1. Kill docker containers holding these ports
for port in 80 443; do
    echo ">>> Checking for Docker containers on port $port..."
    # Check for containers publishing the port
    # 'publish' filter is not supported by docker ps, so we parse output manually.
    container_ids=$(docker ps --format "{{.ID}} {{.Ports}}" | grep ":$port->" | awk '{print $1}' || true)
    if [ -n "$container_ids" ]; then
        echo ">>> Found containers holding port $port: $container_ids"
        docker rm -f $container_ids || true
    else
        echo ">>> No Docker containers found on port $port."
    fi
done

# 2. Kill system processes holding these ports (if lsof is available)
if command -v lsof >/dev/null; then
    echo ">>> lsof is available. Checking for system processes..."
    for port in 80 443; do
        echo ">>> Checking system processes on port $port..."
        pids=$(sudo lsof -t -i :$port -sTCP:LISTEN || true)
        if [ -n "$pids" ]; then
            echo ">>> Found processes holding port $port: $pids. Killing them..."
            sudo kill -9 $pids || true
        else
            echo ">>> No system process found on port $port."
        fi
    done
else
    echo ">>> lsof not found. Skipping system process check."
fi

# 3. Last resort: use fuser to kill anything on tcp ports (if available)
if command -v fuser >/dev/null; then
    echo ">>> fuser is available. Ensuring ports are clear..."
    for port in 80 443; do
        echo ">>> Clearing port $port/tcp..."
        sudo fuser -k -n tcp $port || true
    done
fi

# Verification: Check if ports are actually free
echo ">>> Verifying ports 80 and 443 are free..."
for port in 80 443; do
    # Check using lsof if available
    if command -v lsof >/dev/null; then
        if sudo lsof -i :$port -t -sTCP:LISTEN >/dev/null 2>&1; then
             echo "WARNING: Port $port appears to still be in use by:"
             sudo lsof -i :$port -sTCP:LISTEN || true
        else
             echo ">>> Port $port is free (verified by lsof)."
        fi
    else
        # Fallback check using docker (less comprehensive but better than nothing)
        docker_conflict=$(docker ps --format "{{.ID}} {{.Ports}}" | grep ":$port->" || true)
        if [ -n "$docker_conflict" ]; then
             echo "WARNING: A Docker container is still holding port $port:"
             echo "$docker_conflict"
        else
             echo ">>> Port $port is free of Docker containers."
        fi
    fi
done

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
             picka-web picka-nginx picka-certbot \
             picka-frontend picka-server_nginx picka-certbot-init 2>/dev/null || true

# This script is designed to be run by the CI/CD pipeline on the production server.
# It handles the initial Let's Encrypt certificate generation automatically.

DOMAIN="pickaladder.io"
EMAIL="pickaladder@gmail.com"
DATA_PATH="./certbot"
CERT_DIR="$DATA_PATH/conf/live/$DOMAIN"

echo ">>> Checking for existing certificate at $CERT_DIR..."

# Check for dummy certificate or incomplete state
if [ -d "$CERT_DIR" ]; then
    if [ -f "$CERT_DIR/fullchain.pem" ]; then
        if sudo openssl x509 -in "$CERT_DIR/fullchain.pem" -text -noout | grep -q "CN.*=.*localhost"; then
            echo ">>> Detected dummy certificate. Removing to force regeneration..."
            sudo rm -rf "$CERT_DIR"
            sudo rm -rf "$DATA_PATH/conf/archive/$DOMAIN"
            sudo rm -rf "$DATA_PATH/conf/renewal/$DOMAIN.conf"
        fi
    else
        echo ">>> Certificate directory exists but fullchain.pem is missing. Removing..."
        sudo rm -rf "$CERT_DIR"
        sudo rm -rf "$DATA_PATH/conf/archive/$DOMAIN"
        sudo rm -rf "$DATA_PATH/conf/renewal/$DOMAIN.conf"
    fi
fi

# The main deployment logic is wrapped in this if/else block.
# If a certificate already exists, we just start the services.
# If not, we run the one-time generation process.
if [ -d "$CERT_DIR" ]; then
    echo "Certificate found. Starting services..."
else
    echo "Certificate not found. Starting first-time generation process..."

    # Ensure clean slate
    sudo rm -rf "$DATA_PATH/conf/archive/$DOMAIN"
    sudo rm -rf "$DATA_PATH/conf/renewal/$DOMAIN.conf"

    # Create webroot directory with proper permissions
    echo ">>> Creating webroot directory..."
    sudo mkdir -p "$DATA_PATH/www"
    sudo chmod -R 755 "$DATA_PATH/www"

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
    if ! docker-compose -f docker-compose.prod.yml up -d web nginx; then
        echo "ERROR: Failed to start web and nginx."
        echo ">>> Diagnostic info:"
        echo "--- docker ps -a ---"
        docker ps -a || true
        echo "--- netstat/ss ---"
        sudo ss -lptn || sudo netstat -tulpn || true
        exit 1
    fi

    # Wait for Nginx to be fully up and running
    echo ">>> Waiting for Nginx to launch on port 80..."
    RETRIES=0
    while ! curl -s --head http://localhost > /dev/null; do
        RETRIES=$((RETRIES+1))
        if [ $RETRIES -gt 60 ]; then
             echo "Error: Nginx failed to start after 60 seconds."
             exit 1
        fi
        sleep 1
    done
    echo ">>> Nginx is up!"

    # Verify that Nginx can serve files from the webroot
    echo ">>> Verifying Nginx webroot serving..."
    mkdir -p "$DATA_PATH/www/.well-known/acme-challenge"
    echo "success" > "$DATA_PATH/www/.well-known/acme-challenge/test-challenge"

    # 1. Check via localhost (catches basic mount issues)
    if curl -s "http://localhost/.well-known/acme-challenge/test-challenge" | grep -q "success"; then
        echo ">>> Nginx is correctly serving challenge files (via localhost)."
    else
        echo "Error: Nginx failed to serve test challenge file via localhost."
        echo "Debug: curl output:"
        curl -v "http://localhost/.well-known/acme-challenge/test-challenge"
        exit 1
    fi

    # 2. Check via Host header (catches server block config issues)
    if curl -s -H "Host: $DOMAIN" "http://localhost/.well-known/acme-challenge/test-challenge" | grep -q "success"; then
        echo ">>> Nginx is correctly serving challenge files (via Host: $DOMAIN)."
    else
        echo "Error: Nginx failed to serve test challenge file via Host header."
        echo "Debug: curl output:"
        curl -v -H "Host: $DOMAIN" "http://localhost/.well-known/acme-challenge/test-challenge"
        exit 1
    fi

    # 3. Replace the dummy certificate with a real one from Let's Encrypt.
    # We remove the dummy files before certbot runs.
    echo ">>> Requesting real certificate from Let's Encrypt..."
    sudo rm -rf $CERT_DIR
    docker-compose -f docker-compose.prod.yml run --name picka-certbot-init --rm --entrypoint certbot certbot certonly --webroot \
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
