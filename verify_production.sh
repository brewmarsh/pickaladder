#!/bin/bash

echo "========================================"
echo "      Pickaladder HTTPS Debugger        "
echo "========================================"

# Container Names (defined in docker-compose.prod.yml)
NGINX_CONTAINER="picka-server_nginx"
WEB_CONTAINER="picka-frontend"
CERTBOT_CONTAINER="picka-certbot"

# 1. Check Containers
echo -e "\n>>> 1. Checking Container Status..."
if docker ps -a --format '{{.Names}}\t{{.Status}}' | grep "picka-"; then
    echo "Found picka containers."
    docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep "picka-"
else
    echo "WARNING: No containers with name containing 'picka-' found."
fi

# 2. Check Certificates
echo -e "\n>>> 2. Checking Let's Encrypt Certificates..."
# Check if Nginx container is running before exec
if docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
    if docker exec "$NGINX_CONTAINER" test -f /etc/letsencrypt/live/pickaladder.io/fullchain.pem; then
        echo " [OK] Certificate file found."
        echo "      Details:"
        docker exec "$NGINX_CONTAINER" openssl x509 -in /etc/letsencrypt/live/pickaladder.io/fullchain.pem -text -noout | grep "Issuer\|Subject:\|Not After" || echo " (openssl not found in container - try redeploying to get updated image)"
    else
        echo " [FAIL] Certificate file NOT found in the Nginx container."
    fi
else
    echo " [SKIP] Nginx container ($NGINX_CONTAINER) is not running. Cannot check certs inside it."
fi

# 3. Check Nginx Logs for Errors
echo -e "\n>>> 3. Checking Recent Nginx Logs..."
docker logs --tail=30 "$NGINX_CONTAINER" 2>&1 || echo "Could not read logs for $NGINX_CONTAINER"

# 4. Check Certbot Logs
echo -e "\n>>> 4. Checking Recent Certbot Logs..."
docker logs --tail=30 "$CERTBOT_CONTAINER" 2>&1 || echo "Could not read logs for $CERTBOT_CONTAINER"

# 5. Check Connectivity from Nginx to Web
echo -e "\n>>> 5. Testing Connectivity (Nginx -> Web)..."
if docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
    # Check if netcat is available
    if docker exec "$NGINX_CONTAINER" which nc > /dev/null 2>&1; then
        # In docker compose, the host is the service name 'web'.
        if docker exec "$NGINX_CONTAINER" nc -z -v web 27272; then
            echo " [OK] Nginx can reach 'web' on port 27272."
        else
            echo " [FAIL] Nginx CANNOT reach 'web' on port 27272."
            echo "        Trying container name '$WEB_CONTAINER'..."
             if docker exec "$NGINX_CONTAINER" nc -z -v "$WEB_CONTAINER" 27272; then
                 echo " [OK] Nginx can reach '$WEB_CONTAINER' on port 27272."
             else
                 echo " [FAIL] Nginx CANNOT reach '$WEB_CONTAINER' either."
             fi
        fi
    else
        echo " [WARN] 'nc' (netcat) not found in Nginx container. Skipping connectivity test."
    fi
else
     echo " [SKIP] Nginx container is not running."
fi

echo -e "\n========================================"
echo " Troubleshooting Tips:"
echo " 1. If containers are missing, ensure the deployment ran successfully."
echo " 2. If certs are missing, check Certbot logs above for validation errors."
echo "========================================"
