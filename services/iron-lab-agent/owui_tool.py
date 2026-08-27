"""
title: Iron Lab Host
author: Iron Security
description: Interact with the local Ubuntu host (iron-tools) via Iron Lab Agent — list/read/write files, run allowlisted commands, manage services.
required_open_webui_version: 0.6.0
requirements: requests
version: 1.0.0
licence: MIT
"""

from __future__ import annotations

import json
from typing import Optional

import requests
from pydantic import BaseModel, Field


class Tools:
    def __init__(self):
        self.valves = self.Valves()

    class Valves(BaseModel):
        agent_url: str = Field(
            default="http://172.19.0.1:8793",
            description="Iron Lab Agent base URL (OWUI docker bridge gateway, or host.docker.internal:8793)",
        )
        api_token: str = Field(
            default="",
            description="Bearer token (IRON_LAB_TOKEN). Prefer setting via tool valves.",
        )
        timeout_sec: int = Field(default=120, description="HTTP timeout seconds")

    def _headers(self) -> dict:
        token = (self.valves.api_token or "").strip()
        if not token:
            raise Exception("Iron Lab Tool: api_token valve is empty — set IRON_LAB_TOKEN in tool valves.")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return self.valves.agent_url.rstrip("/") + path

    def _fmt(self, data) -> str:
        return json.dumps(data, ensure_ascii=False, indent=2)

    def lab_health(self) -> str:
        """
        Check that the Iron Lab Agent on the Ubuntu host is reachable.
        """
        r = requests.get(self._url("/health"), headers=self._headers(), timeout=self.valves.timeout_sec)
        r.raise_for_status()
        return self._fmt(r.json())

    def lab_list(self, path: str = "/home/ubuntu/iron-tools") -> str:
        """
        List files and directories under an allowlisted host path (default: iron-tools).
        :param path: Absolute path under /home/ubuntu/iron-tools (or other allowlisted roots)
        """
        r = requests.get(
            self._url("/v1/list"),
            params={"path": path},
            headers=self._headers(),
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_read(self, path: str) -> str:
        """
        Read a text file from the Ubuntu host (allowlisted roots only).
        :param path: Absolute file path to read
        """
        r = requests.get(
            self._url("/v1/read"),
            params={"path": path},
            headers=self._headers(),
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_write(self, path: str, content: str, backup: bool = True) -> str:
        """
        Write/overwrite a text file on the Ubuntu host (creates .bak-<timestamp> by default).
        :param path: Absolute file path to write
        :param content: Full new file contents
        :param backup: Create a timestamped backup before overwrite
        """
        r = requests.put(
            self._url("/v1/write"),
            headers=self._headers(),
            json={"path": path, "content": content, "backup": backup},
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_run(self, argv_json: str, cwd: str = "/home/ubuntu/iron-tools") -> str:
        """
        Run an allowlisted command on the host. Pass argv as a JSON array of strings (no shell).
        Examples:
          ["git","status"]
          ["docker","compose","ps"]
          ["systemctl","status","open-webui"]
          ["rg","-n","LlmManagerModal","Iron-maverick-agent-pentest"]
        :param argv_json: JSON array of command argv, e.g. ["git","diff"]
        :param cwd: Working directory under allowlisted roots
        """
        try:
            argv = json.loads(argv_json)
        except json.JSONDecodeError as e:
            return f"Invalid argv_json (must be JSON array): {e}"
        if not isinstance(argv, list):
            return "argv_json must be a JSON array of strings"
        r = requests.post(
            self._url("/v1/run"),
            headers=self._headers(),
            json={"argv": argv, "cwd": cwd},
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_service(self, name: str, action: str = "status") -> str:
        """
        Control an allowlisted systemd service on the host.
        Allowed names: open-webui, iron-hub, qwen-uncensored, iron-lab-agent, nginx
        Allowed actions: status, is-active, restart, reload
        :param name: Service unit name (without .service)
        :param action: status | is-active | restart | reload
        """
        r = requests.post(
            self._url("/v1/service"),
            headers=self._headers(),
            json={"name": name, "action": action},
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_git_status(self, path: str = "/home/ubuntu/iron-tools") -> str:
        """
        git status --short --branch in an allowlisted repo path.
        :param path: Repository path
        """
        r = requests.get(
            self._url("/v1/git"),
            params={"path": path, "action": "status"},
            headers=self._headers(),
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"

    def lab_git_diff(self, path: str = "/home/ubuntu/iron-tools") -> str:
        """
        git diff for an allowlisted repo path.
        :param path: Repository path
        """
        r = requests.get(
            self._url("/v1/git"),
            params={"path": path, "action": "diff"},
            headers=self._headers(),
            timeout=self.valves.timeout_sec,
        )
        return self._fmt(r.json()) if r.content else f"HTTP {r.status_code}"
