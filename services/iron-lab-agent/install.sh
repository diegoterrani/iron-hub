#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if [[ ! -f .env ]] || ! grep -q '^IRON_LAB_TOKEN=.\+' .env; then
  umask 077
  printf 'IRON_LAB_TOKEN=%s\n' "$(openssl rand -hex 32)" > .env
  chmod 600 .env
  echo "created $DIR/.env"
fi

grep -qxF '.env' .gitignore 2>/dev/null || echo '.env' >> .gitignore

sudo cp "$DIR/deploy/iron-lab-agent.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iron-lab-agent
systemctl is-active iron-lab-agent

# Ensure OWUI has tools enabled
cd "$DIR/../open-webui"
docker compose up -d

set -a
# shellcheck disable=SC1091
source "$DIR/.env"
set +a

docker cp "$DIR/owui_tool.py" open-webui:/tmp/owui_tool.py
docker cp "$DIR/register_tool.py" open-webui:/tmp/register_tool.py
docker exec \
  -e IRON_LAB_TOKEN \
  -e IRON_LAB_AGENT_URL=http://host.docker.internal:8793 \
  -e PYTHONPATH=/app/backend \
  -w /app/backend \
  open-webui python3 /tmp/register_tool.py

echo "OK — use model Qwen Local 122B with tool Iron Lab Host"
