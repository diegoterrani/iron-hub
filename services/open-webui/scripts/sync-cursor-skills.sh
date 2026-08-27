#!/usr/bin/env bash
set -euo pipefail
SRC="${1:-/home/ubuntu/.cursor/skills-cursor}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Replace tree (docker cp into an existing dir can leave stale files)
docker exec open-webui rm -rf /skills-cursor
docker cp "$SRC" open-webui:/skills-cursor
docker cp "$SCRIPT_DIR/install_cursor_skills.py" open-webui:/tmp/install_cursor_skills.py
docker exec \
  -e CURSOR_SKILLS_DIR=/skills-cursor \
  -e IRON_LAB_OWNER_EMAIL=iron@hub.local \
  -e IRON_LAB_MODEL_ID=qwen-local \
  -e PYTHONPATH=/app/backend \
  -w /app/backend \
  open-webui python3 /tmp/install_cursor_skills.py
