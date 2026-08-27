#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

PORT="${IRON_HUB_PORT:-3900}"

echo "==> Building frontend..."
cd "$ROOT"
npm install --silent
npm run build

echo "==> Building API..."
rm -rf "$ROOT/api/dist"
cp -r "$ROOT/dist" "$ROOT/api/dist"
cd "$ROOT/api"
go mod tidy
go build -o "$ROOT/iron-hub-server" .

echo "==> Starting Iron Hub on :$PORT (auth gateway)..."
export IRON_HUB_PORT="$PORT"
exec "$ROOT/iron-hub-server"
