from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field


class PlatformCredentials(BaseModel):
    platform: str
    token: str = ""
    refresh_token: str = ""
    email: str = ""
    document: str = ""
    label: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def masked(self) -> dict[str, Any]:
        token = self.token
        if len(token) > 12:
            shown = f"{token[:6]}…{token[-4:]}"
        elif token:
            shown = "••••"
        else:
            shown = ""
        return {
            "platform": self.platform,
            "email": self.email,
            "document": self.document,
            "label": self.label,
            "has_token": bool(self.token),
            "has_refresh_token": bool(self.refresh_token),
            "token_preview": shown,
            "updated_at": self.updated_at.isoformat(),
        }


class CredentialsStore:
    """Local token store (never commit). File mode 600."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        return raw if isinstance(raw, dict) else {}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _from_payload(platform: str, payload: dict[str, Any]) -> PlatformCredentials:
        # Older saves nested `platform` inside the value; avoid duplicate kwarg.
        clean = {k: v for k, v in payload.items() if k != "platform"}
        return PlatformCredentials(platform=platform, **clean)

    def list(self) -> list[dict[str, Any]]:
        out = []
        for platform, payload in self._read().items():
            if not isinstance(payload, dict):
                continue
            out.append(self._from_payload(platform, payload).masked())
        return out

    def get(self, platform: str) -> Optional[PlatformCredentials]:
        data = self._read().get(platform)
        if not isinstance(data, dict):
            return None
        return self._from_payload(platform, data)

    def get_token(self, platform: str) -> str:
        cred = self.get(platform)
        return cred.token if cred else ""

    def get_refresh_token(self, platform: str) -> str:
        cred = self.get(platform)
        return cred.refresh_token if cred else ""

    @staticmethod
    def _clean_secret(value: str) -> str:
        text = (value or "").strip()
        if text.lower().startswith("bearer "):
            text = text[7:].strip()
        if (text.startswith('"') and text.endswith('"')) or (
            text.startswith("'") and text.endswith("'")
        ):
            text = text[1:-1].strip()
        return text.replace("\n", "").replace("\r", "").strip()

    def save(
        self,
        platform: str,
        token: str,
        email: str = "",
        document: str = "",
        label: str = "",
        refresh_token: str = "",
    ) -> dict[str, Any]:
        data = self._read()
        prev = data.get(platform) if isinstance(data.get(platform), dict) else {}
        cleaned_refresh = self._clean_secret(refresh_token)
        next_refresh = cleaned_refresh or str(prev.get("refresh_token") or "")
        cred = PlatformCredentials(
            platform=platform,
            token=self._clean_secret(token),
            refresh_token=self._clean_secret(next_refresh),
            email=email or str(prev.get("email") or ""),
            document=document or str(prev.get("document") or ""),
            label=label or str(prev.get("label") or ""),
        )
        # Persist without duplicating platform in the nested object
        payload = cred.model_dump(mode="json")
        payload.pop("platform", None)
        data[platform] = payload
        self._write(data)
        return cred.masked()

    def delete(self, platform: str) -> bool:
        data = self._read()
        if platform not in data:
            return False
        del data[platform]
        self._write(data)
        return True
