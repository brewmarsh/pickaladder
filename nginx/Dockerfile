FROM nginx:alpine

# Install netcat-openbsd to get the 'nc' command for the entrypoint script.
RUN apk add --no-cache netcat-openbsd

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
