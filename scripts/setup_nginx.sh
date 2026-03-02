#!/bin/bash
# Nginx setup script for pickaladder

# 1. Link the file to sites-enabled
sudo ln -sf /etc/nginx/sites-available/pickaladder /etc/nginx/sites-enabled/

# 2. Test the Nginx config syntax
sudo nginx -t

# 3. Reload Nginx
sudo systemctl reload nginx

# 4. Run Certbot to obtain SSL certificates
sudo certbot --nginx -d app.pickaladder.io -d www.app.pickaladder.io
