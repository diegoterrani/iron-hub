#!/usr/bin/env bash
# Poll DNS + HTTP-01 reachability, then issue Let's Encrypt and enable HTTPS.
set -euo pipefail

DOMAIN="${DOMAIN:-irontools.iron-security.com}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="${LOG:-/tmp/irontools-le-issue.log}"
PUBLIC_IP="$(curl -4 -sS --max-time 5 ifconfig.me || true)"

exec >>"$LOG" 2>&1
echo "==== $(date -Is) wait-and-issue start (domain=${DOMAIN} ip=${PUBLIC_IP}) ===="

for i in $(seq 1 120); do
  A="$(dig +short "${DOMAIN}" A @1.1.1.1 | head -1 || true)"
  [[ -z "${A}" ]] && A="$(dig +short "${DOMAIN}" A @8.8.8.8 | head -1 || true)"
  echo "$(date -Is) try=${i} A=${A:-none}"

  if [[ -n "${A}" ]]; then
    sudo mkdir -p /var/www/certbot/.well-known/acme-challenge
    echo "le-ok" | sudo tee /var/www/certbot/.well-known/acme-challenge/probe.txt >/dev/null
    if [[ -n "${PUBLIC_IP}" && "${A}" != "${PUBLIC_IP}" ]]; then
      echo "NOTE: A=${A} != public IP ${PUBLIC_IP} (proxy/ALB?). Continuing anyway."
    fi
    # Preflight: LE needs inbound TCP/80 from the internet
    if ! curl -sS --max-time 8 -o /dev/null "http://${DOMAIN}/.well-known/acme-challenge/probe.txt"; then
      echo "$(date -Is) ACME path not reachable from outside (open SG TCP 80/443). retrying…"
      sleep 30
      continue
    fi
    if "${SCRIPT_DIR}/issue-letsencrypt.sh"; then
      echo "$(date -Is) SUCCESS"
      exit 0
    fi
    echo "$(date -Is) issue failed; will retry"
  fi
  sleep 30
done

echo "$(date -Is) FAILED: timed out waiting for DNS/ACME"
exit 1
