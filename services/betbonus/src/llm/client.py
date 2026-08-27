from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

# Shared Iron Red Team LLM (Maverick / Strix OpenRouter)
MAVERICK_ENV = Path(
    "/home/ubuntu/iron-tools/Iron-maverick-agent-pentest/console/server/.env"
)
LOCAL_ENV = Path(__file__).resolve().parents[2] / ".env"


DEFAULT_MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition"
DEEPSEEK_MODEL = "deepseek/deepseek-chat-v3.1"
DOLPHIN_MODEL = DEFAULT_MODEL
LLM_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_config.json"

# Selectable OpenRouter models for BetBonus (chat completions, no tools).
LLM_MODELS: tuple[dict[str, Any], ...] = (
    {
        "id": DOLPHIN_MODEL,
        "aliases": (
            "dolphin-venice",
            f"openrouter/{DOLPHIN_MODEL}",
        ),
        "name": "Dolphin Mistral 24B Venice",
        "description": "Padrão BetBonus · uncensored (Venice), chat-only",
        "max_tokens": 8192,
        "tools": False,
    },
    {
        "id": DEEPSEEK_MODEL,
        "aliases": ("openrouter/deepseek/deepseek-chat-v3.1",),
        "name": "DeepSeek Chat V3.1",
        "description": "OpenRouter · T&Cs e deep attack",
        "max_tokens": 16384,
        "tools": False,
    },
)


def normalize_model_id(model: str) -> str:
    model = (model or "").strip()
    for prefix in ("openrouter/", "openai/", "ollama/", "anthropic/"):
        if model.startswith(prefix):
            model = model[len(prefix) :]
            break
    return model


def resolve_llm_model(model: str) -> dict[str, Any] | None:
    raw = (model or "").strip()
    nid = normalize_model_id(raw)
    for entry in LLM_MODELS:
        aliases = {str(entry["id"]), *(str(a) for a in entry.get("aliases") or ())}
        if raw in aliases or nid in {normalize_model_id(a) for a in aliases}:
            return entry
    return None


def catalog_public() -> list[dict[str, Any]]:
    return [
        {
            "id": e["id"],
            "name": e["name"],
            "description": e["description"],
            "max_tokens": int(e["max_tokens"]),
            "tools": bool(e.get("tools")),
        }
        for e in LLM_MODELS
    ]


def _read_selected_model() -> str:
    try:
        data = json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("model") or "").strip()


def set_iron_llm_model(model: str) -> "LLMConfig":
    entry = resolve_llm_model(model)
    if not entry:
        known = ", ".join(e["id"] for e in LLM_MODELS)
        raise ValueError(f"Modelo não suportado: {model!r}. Opções: {known}")
    LLM_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": entry["id"],
        "name": entry["name"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    LLM_CONFIG_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    LLM_CONFIG_PATH.chmod(0o600)
    return load_iron_llm_config()


@dataclass
class ChatResult:
    text: str
    finish_reason: str = ""
    model: str = ""
    raw: dict[str, Any] | None = None

    @property
    def truncated(self) -> bool:
        return (self.finish_reason or "").lower() in {"length", "max_tokens"}


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                parts.append(str(part.get("text") or part.get("content") or ""))
            elif part:
                parts.append(str(part))
        content = "".join(parts)
    text = str(content or "").strip()
    if text:
        return text
    for key in ("reasoning", "reasoning_content"):
        alt = message.get(key)
        if isinstance(alt, str) and alt.strip():
            return alt.strip()
    return ""


@dataclass
class LLMConfig:
    model: str
    api_key: str
    api_base: str
    http_referer: str = "https://isi.luckygaming.com.br/"
    app_title: str = "Iron Guard BetBonus"
    source: str = "env"
    max_tokens: int = 16384

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    @property
    def chat_model(self) -> str:
        """OpenRouter expects bare id (strip LiteLLM-style prefixes)."""
        return normalize_model_id(self.model)

    def status(self) -> dict[str, Any]:
        key = self.api_key
        masked = f"{key[:6]}…{key[-4:]}" if len(key) > 12 else ("••••" if key else "")
        entry = resolve_llm_model(self.chat_model)
        return {
            "configured": self.configured,
            "model": self.model,
            "chat_model": self.chat_model,
            "name": (entry or {}).get("name") or self.chat_model,
            "api_base": self.api_base,
            "api_key_set": bool(self.api_key),
            "api_key_masked": masked,
            "source": self.source,
            "shared_with": "Iron Maverick / Strix",
            "max_tokens": self.max_tokens,
            "models": catalog_public(),
        }


def _parse_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def load_iron_llm_config() -> LLMConfig:
    """
    Resolve LLM config for BetBonus from Iron Red Team shared sources:

    1. Process environment (incl. systemd EnvironmentFile)
    2. BetBonusAI/.env (optional overlay)
    3. Maverick console/server/.env (shared default)
    """
    # Base: Maverick shared secrets → overlay local BetBonus .env
    file_vars: dict[str, str] = {}
    if MAVERICK_ENV.is_file():
        file_vars.update(_parse_dotenv(MAVERICK_ENV))
    if LOCAL_ENV.is_file():
        file_vars.update(_parse_dotenv(LOCAL_ENV))

    def pick(*keys: str) -> str:
        for key in keys:
            val = (os.environ.get(key) or file_vars.get(key) or "").strip()
            if val:
                return val
        return ""

    env_override = pick("BETBONUS_LLM")
    persisted = _read_selected_model()
    selected_entry = resolve_llm_model(persisted) if persisted else None
    env_entry = resolve_llm_model(env_override) if env_override else None
    default_entry = resolve_llm_model(DEFAULT_MODEL)
    if selected_entry:
        model = selected_entry["id"]
        max_tokens = int(selected_entry["max_tokens"])
        source_model = "ui-select"
    elif env_entry:
        model = env_entry["id"]
        max_tokens = int(env_entry["max_tokens"])
        source_model = ""
    elif default_entry:
        model = default_entry["id"]
        max_tokens = int(default_entry["max_tokens"])
        source_model = ""
    else:
        model = env_override or DEFAULT_MODEL
        max_tokens = 8192
        source_model = ""

    api_key = pick("OPENROUTER_API_KEY", "OPENROUTERKEY", "LLM_API_KEY")
    api_base = pick("LLM_API_BASE", "OPENROUTER_API_BASE") or "https://openrouter.ai/api/v1"
    referer = pick("OPENROUTER_HTTP_REFERER") or "https://isi.luckygaming.com.br/"
    title = pick("OPENROUTER_APP_TITLE") or "Iron Guard BetBonus"

    if source_model:
        source = source_model
    elif any(os.environ.get(k) for k in ("OPENROUTER_API_KEY", "OPENROUTERKEY", "STRIX_LLM", "BETBONUS_LLM")):
        source = "process-env"
    elif LOCAL_ENV.is_file() and MAVERICK_ENV.is_file():
        source = "betbonus.env+maverick.env"
    elif MAVERICK_ENV.is_file():
        source = "maverick.env"
    elif LOCAL_ENV.is_file():
        source = "betbonus.env"
    else:
        source = "defaults"

    return LLMConfig(
        model=model,
        api_key=api_key,
        api_base=api_base.rstrip("/"),
        http_referer=referer,
        app_title=title,
        source=source,
        max_tokens=max_tokens,
    )


class IronLLMClient:
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or load_iron_llm_config()

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: float = 60.0,
        json_mode: bool = False,
    ) -> ChatResult:
        if not self.config.configured:
            raise RuntimeError(
                "LLM não configurada — defina OPENROUTER_API_KEY/STRIX_LLM "
                "(compartilhado com Maverick) ou BetBonusAI/.env"
            )
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.http_referer,
            "X-Title": self.config.app_title,
        }
        cap = int(self.config.max_tokens or max_tokens)
        payload: dict[str, Any] = {
            "model": self.config.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(int(max_tokens), cap),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        def _post(body: dict[str, Any]) -> httpx.Response:
            with httpx.Client(timeout=timeout) as client:
                return client.post(
                    f"{self.config.api_base}/chat/completions",
                    headers=headers,
                    json=body,
                )

        resp = _post(payload)
        if resp.status_code >= 400 and json_mode:
            payload.pop("response_format", None)
            resp = _post(payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        try:
            choice = data["choices"][0]
            message = choice.get("message") or {}
            text = _message_text(message if isinstance(message, dict) else {})
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Resposta LLM inesperada: {json.dumps(data)[:300]}") from exc
        return ChatResult(
            text=text,
            finish_reason=str(choice.get("finish_reason") or ""),
            model=str(data.get("model") or self.config.chat_model),
            raw=data,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        timeout: float = 60.0,
        json_mode: bool = False,
    ) -> str:
        return self.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            json_mode=json_mode,
        ).text

    def ping(self) -> dict[str, Any]:
        try:
            text = self.chat(
                [{"role": "user", "content": "Reply with exactly: OK"}],
                max_tokens=8,
                temperature=0,
                timeout=45.0,
            )
            return {
                "ok": True,
                "reply": text.strip()[:80],
                **self.config.status(),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)[:300], **self.config.status()}
