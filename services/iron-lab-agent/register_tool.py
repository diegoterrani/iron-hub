#!/usr/bin/env python3
"""Register / update the Iron Lab Host tool inside Open WebUI and attach it to qwen-local."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOL_ID = "iron_lab_host"
TOOL_FILE = ROOT / "owui_tool.py"
TOKEN = (os.environ.get("IRON_LAB_TOKEN") or "").strip()
MODEL_ID = os.environ.get("IRON_LAB_MODEL_ID", "qwen-local")
OWNER_EMAIL = os.environ.get("IRON_LAB_OWNER_EMAIL", "iron@hub.local")


async def main() -> int:
    # Must run inside the open-webui container (or an env with open_webui installed + DB).
    from open_webui.models.tools import ToolForm, ToolMeta, Tools
    from open_webui.models.users import Users
    from open_webui.utils.plugin import load_tool_module_by_id, replace_imports
    from open_webui.utils.tools import get_tool_specs
    from open_webui.internal.db import get_async_db_context
    from sqlalchemy import text

    content = TOOL_FILE.read_text(encoding="utf-8")
    content = replace_imports(content)

    # Resolve owner
    async with get_async_db_context() as db:
        row = (
            await db.execute(text("select id, email, role from user where email = :e"), {"e": OWNER_EMAIL})
        ).fetchone()
        if not row:
            row = (await db.execute(text("select id, email, role from user where role = 'admin' limit 1"))).fetchone()
        if not row:
            print("ERROR: no admin user in Open WebUI DB", file=sys.stderr)
            return 1
        user_id, email, role = row[0], row[1], row[2]
        print(f"owner: {email} ({user_id}) role={role}")

    tool_module, frontmatter = await load_tool_module_by_id(TOOL_ID, content=content)
    specs = get_tool_specs(tool_module)
    print(f"specs: {len(specs)} methods -> {[s.get('name') for s in specs]}")

    form = ToolForm(
        id=TOOL_ID,
        name="Iron Lab Host",
        content=content,
        meta=ToolMeta(
            description="Host lab tools for Ubuntu iron-tools development (allowlisted).",
            manifest=frontmatter or {},
            has_user_valves=hasattr(tool_module, "UserValves"),
        ),
        access_grants=[],
    )

    existing = await Tools.get_tool_by_id(TOOL_ID)
    if existing:
        updated = await Tools.update_tool_by_id(
            TOOL_ID,
            {
                "name": form.name,
                "content": form.content,
                "meta": form.meta.model_dump(),
                "specs": specs,
            },
        )
        print("updated tool:", TOOL_ID, bool(updated))
    else:
        created = await Tools.insert_new_tool(user_id, form, specs)
        print("created tool:", TOOL_ID, bool(created))

    # Set valves (agent URL + token)
    valves = {
        "agent_url": os.environ.get("IRON_LAB_AGENT_URL", "http://host.docker.internal:8793"),
        "api_token": TOKEN,
        "timeout_sec": 120,
    }
    if not TOKEN:
        print("WARNING: IRON_LAB_TOKEN empty — set tool valves manually in Workspace", file=sys.stderr)
    await Tools.update_tool_valves_by_id(TOOL_ID, valves)
    print("valves set")

    # Attach tool to workspace model
    async with get_async_db_context() as db:
        row = (await db.execute(text("select meta, params from model where id = :id"), {"id": MODEL_ID})).fetchone()
        if not row:
            print(f"WARNING: model {MODEL_ID} not found — enable the tool manually in Workspace → Models", file=sys.stderr)
            return 0
        meta = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
        params = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or {})
        tool_ids = list(meta.get("toolIds") or [])
        if TOOL_ID not in tool_ids:
            tool_ids.append(TOOL_ID)
        meta["toolIds"] = tool_ids
        caps = dict(meta.get("capabilities") or {})
        # Help native/default function calling UIs
        if "tools" not in caps:
            caps["tools"] = True
        meta["capabilities"] = caps
        if not params.get("function_calling"):
            params["function_calling"] = "native"
        await db.execute(
            text("update model set meta = :m, params = :p, updated_at = strftime('%s','now') where id = :id"),
            {"m": json.dumps(meta), "p": json.dumps(params), "id": MODEL_ID},
        )
        await db.commit()
        print(f"model {MODEL_ID}: toolIds={tool_ids} function_calling={params.get('function_calling')}")

    return 0


if __name__ == "__main__":
    # update_tool_valves_by_id signature may vary — probe
    raise SystemExit(asyncio.run(main()))
