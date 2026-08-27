#!/usr/bin/env bash
# Enable https://llm.irontools.iron-security.com/ (Open WebUI on nginx :443)
# Prerequisite DNS:  llm.irontools.iron-security.com  A  <this-host-public-ip>
set -euo pipefail

DOMAIN=llm.irontools.iron-security.com
WEBROOT=/var/www/certbot
LIVE=/etc/letsencrypt/live/$DOMAIN
SRC_DIR=/home/ubuntu/iron-tools/iron-hub/deploy

echo "==> Checking DNS for $DOMAIN"
IP="$(dig +short "$DOMAIN" A @8.8.8.8 | tail -1)"
PUB="$(curl -sS --max-time 3 -H "X-aws-ec2-metadata-token: $(curl -sS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" http://169.254.169.254/latest/meta-data/public-ipv4 || true)"
echo "    DNS A=$IP  host public=$PUB"
if [[ -z "$IP" || "$IP" == *"NXDOMAIN"* ]]; then
  echo "ERROR: create DNS A record first:"
  echo "  $DOMAIN  A  ${PUB:-<EC2 public IP>}"
  exit 1
fi

sudo mkdir -p "$WEBROOT"
if [[ ! -f "$LIVE/fullchain.pem" ]]; then
  echo "==> Requesting Let's Encrypt cert"
  sudo certbot certonly --webroot -w "$WEBROOT" -d "$DOMAIN" \
    --non-interactive --agree-tos --register-unsafely-without-email
fi

echo "==> Installing nginx vhost"
sudo cp "$SRC_DIR/nginx-llm-irontools.conf" /etc/nginx/sites-available/llm-irontools
sudo ln -sf /etc/nginx/sites-available/llm-irontools /etc/nginx/sites-enabled/llm-irontools
sudo cp "$SRC_DIR/nginx-irontools.conf" /etc/nginx/sites-available/irontools-hub
sudo nginx -t
sudo systemctl reload nginx

echo "==> Restart Open WebUI + Hub (gateway URL)"
cd /home/ubuntu/iron-tools/iron-hub/services/open-webui && docker compose up -d
cd /home/ubuntu/iron-tools/iron-hub/api && go build -o ../iron-hub-server .
sudo systemctl restart iron-hub

echo "OK → https://$DOMAIN/"
echo "Flow: login Hub → open Open WebUI card (or open subdomain after session cookie exists)"
