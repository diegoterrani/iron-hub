#!/usr/bin/env bash
# Issue / renew Let's Encrypt cert for irontools.iron-security.com and enable HTTPS nginx.
set -euo pipefail

DOMAIN="${DOMAIN:-irontools.iron-security.com}"
EMAIL="${EMAIL:-admin@iron-security.com}"
WEBROOT="${WEBROOT:-/var/www/certbot}"
NGINX_SITE_SRC="$(cd "$(dirname "$0")" && pwd)/nginx-irontools.conf"
NGINX_SITE_DST="/etc/nginx/sites-available/irontools-hub"

echo "==> Checking DNS for ${DOMAIN}"
RESOLVED="$(dig +short "${DOMAIN}" A @1.1.1.1 | head -1 || true)"
[[ -z "${RESOLVED}" ]] && RESOLVED="$(dig +short "${DOMAIN}" A @8.8.8.8 | head -1 || true)"
PUBLIC_IP="$(curl -4 -sS --max-time 5 ifconfig.me || true)"
echo "    A record: ${RESOLVED:-<none>}"
echo "    Public IP: ${PUBLIC_IP:-<unknown>}"

if [[ -z "${RESOLVED}" ]]; then
  echo "ERROR: ${DOMAIN} has no public A record yet."
  echo "Create in Cloudflare (DNS only / grey cloud recommended for first issue):"
  echo "  Type A  Name irontools  Content ${PUBLIC_IP:-<this-host-public-ip>}  Proxy OFF"
  exit 1
fi

sudo mkdir -p "${WEBROOT}"
sudo certbot certonly \
  --webroot -w "${WEBROOT}" \
  -d "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --non-interactive \
  --keep-until-expiring \
  --rsa-key-size 2048

# Ensure ssl helpers exist (certbot packages them)
if [[ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]]; then
  sudo curl -fsSL -o /etc/letsencrypt/options-ssl-nginx.conf \
    https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf
fi
if [[ ! -f /etc/letsencrypt/ssl-dhparams.pem ]]; then
  sudo openssl dhparam -out /etc/letsencrypt/ssl-dhparams.pem 2048
fi

echo "==> Installing HTTPS nginx site"
sudo cp "${NGINX_SITE_SRC}" "${NGINX_SITE_DST}"
sudo ln -sfn "${NGINX_SITE_DST}" /etc/nginx/sites-enabled/irontools-hub
sudo nginx -t
sudo systemctl reload nginx

echo "==> Done. Hub: https://${DOMAIN}/"
curl -sS -o /dev/null -w "HTTPS check: %{http_code}\n" "https://${DOMAIN}/" || true
