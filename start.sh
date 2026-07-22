#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
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

echo "==> Starting Iron Hub on :$PORT..."
export IRON_HUB_PORT="$PORT"
exec "$ROOT/iron-hub-server"
