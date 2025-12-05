#!/bin/bash
set -e

# Define certificate directory
CERT_DIR="nginx/ssl"

# Create directory if it doesn't exist
if [ ! -d "$CERT_DIR" ]; then
    echo "Creating directory $CERT_DIR..."
    mkdir -p "$CERT_DIR"
fi

# Check if certificates already exist
if [ -f "$CERT_DIR/self-signed.crt" ] && [ -f "$CERT_DIR/self-signed.key" ]; then
    echo "Certificates already exist in $CERT_DIR."
    read -p "Do you want to overwrite them? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborting."
        exit 0
    fi
fi

echo "Generating self-signed certificate..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/self-signed.key" \
    -out "$CERT_DIR/self-signed.crt" \
    -subj "/C=US/ST=Dev/L=Dev/O=Pickaladder/CN=localhost"

echo "Success! Certificates generated at:"
echo " - $CERT_DIR/self-signed.crt"
echo " - $CERT_DIR/self-signed.key"
