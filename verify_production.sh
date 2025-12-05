#!/bin/bash

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    DOCKER_COMPOSE="docker compose"
fi

echo "Using command: $DOCKER_COMPOSE"

echo "========================================"
echo "      Pickaladder HTTPS Debugger        "
echo "========================================"

# 1. Check Containers
echo -e "\n>>> 1. Checking Container Status..."
$DOCKER_COMPOSE -f docker-compose.prod.yml ps

# 2. Check Certificates
echo -e "\n>>> 2. Checking Let's Encrypt Certificates..."
if $DOCKER_COMPOSE -f docker-compose.prod.yml exec nginx test -f /etc/letsencrypt/live/pickaladder.io/fullchain.pem; then
    echo " [OK] Certificate file found."
    echo "      Details:"
    # This might fail if openssl is not installed in the running container yet (requires rebuild)
    $DOCKER_COMPOSE -f docker-compose.prod.yml exec nginx openssl x509 -in /etc/letsencrypt/live/pickaladder.io/fullchain.pem -text -noout | grep "Issuer\|Subject:\|Not After" || echo " (openssl not found in container, try rebuilding)"
else
    echo " [FAIL] Certificate file NOT found in the Nginx container."
fi

# 3. Check Nginx Logs for Errors
echo -e "\n>>> 3. Checking Recent Nginx Logs..."
$DOCKER_COMPOSE -f docker-compose.prod.yml logs --tail=30 nginx

# 4. Check Certbot Logs
echo -e "\n>>> 4. Checking Recent Certbot Logs..."
$DOCKER_COMPOSE -f docker-compose.prod.yml logs --tail=30 certbot

# 5. Check Connectivity from Nginx to Web
echo -e "\n>>> 5. Testing Connectivity (Nginx -> Web)..."
# Check if netcat is available (installed via Dockerfile update)
if $DOCKER_COMPOSE -f docker-compose.prod.yml exec nginx which nc > /dev/null; then
    if $DOCKER_COMPOSE -f docker-compose.prod.yml exec nginx nc -z -v web 27272; then
        echo " [OK] Nginx can reach Web container on port 27272."
    else
        echo " [FAIL] Nginx CANNOT reach Web container."
    fi
else
    echo " [WARN] 'nc' (netcat) not found in Nginx container. Skipping connectivity test. Rebuild to include debugging tools."
fi

echo -e "\n========================================"
echo " Troubleshooting Tips:"
echo " 1. If containers are missing/restarting, check logs above."
echo " 2. If certs are missing, check Certbot logs for validation errors (DNS, firewall)."
echo " 3. If Nginx exits with 'host not found', the web container might be unhealthy."
echo "========================================"
