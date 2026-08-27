#!/usr/bin/env python3
"""Align Open WebUI defaults with OpenRouter (OpenAI-compatible)."""
import json
import os
import sqlite3
import time
import uuid

DB = "/app/backend/data/webui.db"
BASE = os.environ.get("DEFAULT_MODELS", "deepseek/deepseek-chat-v3.1").strip()
DOLPHIN = "cognitivecomputations/dolphin-mistral-24b-venice-edition"
MAX_TOKENS = 16384
OPENAI_BASE = os.environ.get(
    "OPENAI_API_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "").strip()

# Named workspaces (id → OpenRouter model id, display name, tools?, overlay?)
# Dolphin Venice (OpenRouter/Venice) has no tools endpoint — do not send tool specs.
WORKSPACES = [
    {
        "id": "openrouter-default",
        "base": BASE,
        "name": "OpenRouter Default",
        "description": f"OpenRouter default ({BASE}) + Iron Lab Host tools",
        "tools": True,
        "max_tokens": MAX_TOKENS,
    },
    {
        "id": "dolphin-venice",
        "base": DOLPHIN,
        "name": "Dolphin Mistral 24B Venice",
        "description": (
            f"Chat-only ({DOLPHIN}). Venice endpoint does not support tool use "
            "(no Iron Lab Host / lab_git_diff)."
        ),
        "tools": False,
        "max_tokens": 8192,
    },
    {
        # Overlay the raw catalog id so picking it in the picker also skips tools.
        "id": DOLPHIN,
        "base": DOLPHIN,
        "name": "Dolphin Mistral 24B Venice",
        "description": (
            "Chat-only via OpenRouter Venice. This provider has no tools endpoint."
        ),
        "tools": False,
        "overlay": True,
        "max_tokens": 8192,
    },
]


def upsert(c: sqlite3.Connection, key: str, value, now: int) -> None:
    payload = json.dumps(value)
    if c.execute("select 1 from config where key=?", (key,)).fetchone():
        c.execute(
            "update config set value=?, updated_at=? where key=?",
            (payload, now, key),
        )
    else:
        c.execute(
            "insert into config(key, value, updated_at) values (?,?,?)",
            (key, payload, now),
        )
    shown = (
        payload
        if key != "openai.api_keys"
        else json.dumps([f"<redacted len={len(value[0]) if value else 0}>"])
    )
    print("set", key, "=", shown[:160])


def ensure_public_read(c: sqlite3.Connection, resource_id: str, now: int) -> None:
    exists = c.execute(
        "select 1 from access_grant where resource_type=? and resource_id=? "
        "and principal_type=? and principal_id=? and permission=?",
        ("model", resource_id, "user", "*", "read"),
    ).fetchone()
    if exists:
        print("public-read already", resource_id)
        return
    c.execute(
        "insert into access_grant(id, resource_type, resource_id, principal_type, "
        "principal_id, permission, created_at) values (?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "model", resource_id, "user", "*", "read", now),
    )
    print("public-read", resource_id)


BUILTIN_TOOL_CATEGORIES = (
    "time",
    "knowledge",
    "chats",
    "memory",
    "web_search",
    "image_generation",
    "code_interpreter",
    "notes",
    "channels",
    "tasks",
    "automations",
    "calendar",
)


def apply_tool_policy(meta: dict, params: dict, enable_tools: bool, max_tokens: int) -> None:
    params["max_tokens"] = max_tokens
    caps = dict(meta.get("capabilities") or {})
    caps.setdefault("vision", False)
    caps.setdefault("usage", True)
    if enable_tools:
        params["function_calling"] = "native"
        tool_ids = list(meta.get("toolIds") or [])
        if "iron_lab_host" not in tool_ids:
            tool_ids.append("iron_lab_host")
        meta["toolIds"] = tool_ids
        caps["tools"] = True
        caps["skills"] = True
        caps["builtin_tools"] = True
    else:
        # OWUI defaults function_calling to native and injects builtins
        # (get_current_timestamp, notes, calendar, …) unless these are off.
        # Venice/Dolphin has no tools endpoint — must fully opt out.
        params["function_calling"] = "legacy"
        meta["toolIds"] = []
        meta["skillIds"] = []
        meta["builtinTools"] = {cat: False for cat in BUILTIN_TOOL_CATEGORIES}
        caps["tools"] = False
        caps["skills"] = False
        caps["builtin_tools"] = False
    meta["capabilities"] = caps


def upsert_workspace(
    c: sqlite3.Connection,
    workspace_id: str,
    base_model_id: str,
    name: str,
    description: str,
    now: int,
    fallback_user_id: str = "",
    enable_tools: bool = True,
    overlay: bool = False,
    max_tokens: int = MAX_TOKENS,
) -> str:
    row = c.execute(
        "select id, user_id, meta, params from model where id=?",
        (workspace_id,),
    ).fetchone()
    # Migrate legacy alias if creating openrouter-default for the first time
    if not row and workspace_id == "openrouter-default":
        legacy = c.execute(
            "select id, user_id, meta, params from model where id=?",
            ("qwen-local",),
        ).fetchone()
        if legacy:
            workspace_id = "qwen-local"
            row = legacy

    meta = json.loads(row[2] or "{}") if row else {}
    params = json.loads(row[3] or "{}") if row and row[3] else {}
    user_id = (row[1] if row and row[1] else None) or fallback_user_id or ""

    apply_tool_policy(meta, params, enable_tools, max_tokens)
    meta["description"] = description
    stored_base = None if overlay else base_model_id

    if row:
        c.execute(
            "update model set name=?, base_model_id=?, meta=?, params=?, "
            "updated_at=?, is_active=1 where id=?",
            (
                name,
                stored_base,
                json.dumps(meta),
                json.dumps(params),
                now,
                workspace_id,
            ),
        )
    else:
        c.execute(
            "insert into model(id, user_id, base_model_id, name, meta, params, "
            "created_at, updated_at, is_active) values (?,?,?,?,?,?,?,?,1)",
            (
                workspace_id,
                user_id,
                stored_base,
                name,
                json.dumps(meta),
                json.dumps(params),
                now,
                now,
            ),
        )
    print(
        "workspace=",
        workspace_id,
        "base=",
        stored_base,
        "overlay=",
        overlay,
        "name=",
        name,
        "tools=",
        enable_tools,
        "toolIds=",
        meta.get("toolIds"),
    )
    return workspace_id


def main() -> None:
    now = int(time.time())
    c = sqlite3.connect(DB)

    upsert(c, "ui.default_models", BASE, now)
    upsert(c, "models.default_params", {"max_tokens": MAX_TOKENS}, now)
    upsert(c, "openai.enable", True, now)
    upsert(c, "openai.api_base_urls", [OPENAI_BASE], now)
    if OPENAI_KEY:
        upsert(c, "openai.api_keys", [OPENAI_KEY], now)
    else:
        print("WARN: OPENAI_API_KEY unset; leaving openai.api_keys unchanged")

    # Empty model_ids = full OpenRouter catalog (includes Dolphin Venice).
    # Workspace aliases below pin friendly names in the picker.
    upsert(
        c,
        "openai.api_configs",
        {
            "0": {
                "enable": True,
                "tags": [],
                "prefix_id": "",
                "model_ids": [],
                "connection_type": "external",
                "auth_type": "bearer",
            }
        },
        now,
    )

    fallback_user = ""
    row = c.execute(
        "select user_id from model where user_id is not null and user_id != '' limit 1"
    ).fetchone()
    if row:
        fallback_user = row[0]
    if not fallback_user:
        row = c.execute(
            "select id from user where role='admin' order by created_at limit 1"
        ).fetchone()
        if row:
            fallback_user = row[0]

    active_ids = []
    overlay_ids = set()
    for spec in WORKSPACES:
        actual_id = upsert_workspace(
            c,
            spec["id"],
            spec["base"],
            spec["name"],
            spec["description"],
            now,
            fallback_user_id=fallback_user,
            enable_tools=bool(spec.get("tools", True)),
            overlay=bool(spec.get("overlay", False)),
            max_tokens=int(spec.get("max_tokens") or MAX_TOKENS),
        )
        ensure_public_read(c, actual_id, now)
        if spec.get("overlay"):
            overlay_ids.add(actual_id)
        else:
            active_ids.append(actual_id)

    # Pinned + ordered so Dolphin appears as a first-class picker option.
    # Comma-separated: OWUI frontend splits default_pinned_models on ",".
    # Pin the no-tools workspace, not the raw catalog id (avoids sending lab tools).
    dolphin_ws = next((i for i in active_ids if i == "dolphin-venice"), None)
    others = [i for i in active_ids if i != "dolphin-venice"]
    pinned = []
    for mid in (dolphin_ws, *others, BASE):
        if mid and mid not in pinned:
            pinned.append(mid)
    upsert(c, "ui.default_pinned_models", ",".join(pinned), now)
    upsert(c, "ui.model_order_list", pinned, now)

    c.commit()
    for key in (
        "ui.default_models",
        "ui.default_pinned_models",
        "ui.model_order_list",
        "openai.api_base_urls",
        "openai.api_configs",
    ):
        print(
            "verify",
            key,
            c.execute("select value from config where key=?", (key,)).fetchone()[0][
                :240
            ],
        )


if __name__ == "__main__":
    main()
