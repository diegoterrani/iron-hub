#!/usr/bin/env python3
"""Iron Lab Agent — allowlisted host API for Open WebUI Tools.

Binds to 127.0.0.1 only. Auth: Bearer token (IRON_LAB_TOKEN).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("IRON_LAB_CONFIG", ROOT / "config.json"))
TOKEN = (os.environ.get("IRON_LAB_TOKEN") or "").strip()


def load_config() -> dict[str, Any]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["roots"] = [str(Path(p).resolve()) for p in cfg.get("roots", [])]
    cfg["extra_read_files"] = [str(Path(p).resolve()) for p in cfg.get("extra_read_files", [])]
    cfg["services"] = list(cfg.get("services", []))
    return cfg


def discover_listen_hosts(mode: str | list[str]) -> list[str]:
    """Bind local + docker bridge gateways (not the public NIC)."""
    if isinstance(mode, list):
        return mode
    if mode not in {"docker+local", "docker"}:
        return [mode]

    hosts = []
    if mode == "docker+local":
        hosts.append("127.0.0.1")

    # Parse `ip -4 -o addr show` for docker0 / br-* only
    try:
        out = subprocess.check_output(["ip", "-4", "-o", "addr", "show"], text=True)
    except Exception:  # noqa: BLE001
        out = ""
    for line in out.splitlines():
        # 3: docker0    inet 172.17.0.1/16 ...
        parts = line.split()
        if len(parts) < 4:
            continue
        iface, inet = parts[1].rstrip(":"), parts[2]
        if inet != "inet":
            continue
        if not (iface == "docker0" or iface.startswith("br-")):
            continue
        ip = parts[3].split("/")[0]
        if ip not in hosts:
            hosts.append(ip)
    if not hosts:
        hosts = ["127.0.0.1"]
    return hosts


CFG = load_config()


def json_response(handler: BaseHTTPRequestHandler, code: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    if not TOKEN:
        return False
    auth = handler.headers.get("Authorization") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip() == TOKEN
    return (handler.headers.get("X-Iron-Lab-Token") or "").strip() == TOKEN


def resolve_under_roots(path: str, *, write: bool = False) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(CFG["roots"][0]) / p
    resolved = p.resolve()
    resolved_s = str(resolved)

    if write:
        for root in CFG["roots"]:
            if resolved_s == root or resolved_s.startswith(root + os.sep):
                return resolved
        raise PermissionError(f"path outside writable roots: {resolved}")

    for root in CFG["roots"]:
        if resolved_s == root or resolved_s.startswith(root + os.sep):
            return resolved
    for extra in CFG["extra_read_files"]:
        if resolved_s == extra:
            return resolved
    raise PermissionError(f"path outside allowlist: {resolved}")


def backup_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = path.with_name(path.name + f".bak-{ts}")
    shutil.copy2(path, bak)
    return str(bak)


SHELL_META = re.compile(r"[|;&`$<>\\\n\r]")


def validate_argv(argv: list[str], cwd: Path) -> None:
    if not argv or not isinstance(argv, list):
        raise ValueError("argv must be a non-empty list")
    if any(not isinstance(a, str) or not a for a in argv):
        raise ValueError("argv entries must be non-empty strings")
    if any(SHELL_META.search(a) for a in argv):
        raise ValueError("shell metacharacters are not allowed")

    head = argv[0]
    allowed_bins = {
        "git",
        "ls",
        "find",
        "rg",
        "grep",
        "sed",
        "head",
        "tail",
        "wc",
        "python3",
        "npm",
        "npx",
        "node",
        "go",
        "docker",
        "nginx",
        "systemctl",
        "journalctl",
        "curl",
        "make",
        "bash",
    }
    if head not in allowed_bins:
        raise PermissionError(f"binary not allowlisted: {head}")

    # Tight rules for high-risk binaries
    if head == "bash":
        if argv[1:2] != ["-lc"] or len(argv) != 3:
            raise PermissionError("bash only allowed as: bash -lc '<allowlisted script>'")
        script = argv[2]
        if not re.fullmatch(r"(npm ci|npm run build|go build\b.*|python3 -m compileall\b.*)", script):
            raise PermissionError(f"bash script not allowlisted: {script}")
    elif head == "systemctl":
        if len(argv) < 3:
            raise PermissionError("systemctl requires action + unit")
        action, unit = argv[1], argv[2]
        if action not in {"status", "is-active", "restart", "reload", "show"}:
            raise PermissionError(f"systemctl action not allowed: {action}")
        if unit not in CFG["services"] and unit.rstrip(".service") not in CFG["services"]:
            raise PermissionError(f"systemctl unit not allowlisted: {unit}")
    elif head == "docker":
        # docker compose … inside allowlisted cwd only
        if argv[1:2] != ["compose"]:
            raise PermissionError("only docker compose is allowed")
        sub = argv[2] if len(argv) > 2 else ""
        if sub not in {"ps", "logs", "up", "restart", "down", "build", "pull", "config"}:
            raise PermissionError(f"docker compose subcommand not allowed: {sub}")
    elif head == "git":
        sub = argv[1] if len(argv) > 1 else ""
        if sub not in {"status", "diff", "log", "show", "branch", "rev-parse", "add", "commit", "stash", "checkout"}:
            raise PermissionError(f"git subcommand not allowed: {sub}")
        if sub == "checkout" and "--" not in argv:
            # allow restore of specific files: git checkout -- path
            raise PermissionError("git checkout only allowed with -- <paths>")
    elif head == "nginx" and argv[1:] not in (["-t"],):
        raise PermissionError("nginx only allowed as: nginx -t")
    elif head == "journalctl":
        # journalctl -u UNIT -n N --no-pager
        if "-u" not in argv:
            raise PermissionError("journalctl requires -u <unit>")
        uidx = argv.index("-u")
        unit = argv[uidx + 1] if uidx + 1 < len(argv) else ""
        if unit not in CFG["services"] and unit.rstrip(".service") not in CFG["services"]:
            raise PermissionError(f"journalctl unit not allowlisted: {unit}")

    cwd_s = str(cwd.resolve())
    if not any(cwd_s == r or cwd_s.startswith(r + os.sep) for r in CFG["roots"]):
        raise PermissionError(f"cwd outside roots: {cwd}")


def run_argv(argv: list[str], cwd: str | None) -> dict[str, Any]:
    work = resolve_under_roots(cwd or CFG["roots"][0], write=False)
    if not work.is_dir():
        # if file path given, use parent
        work = work if work.is_dir() else work.parent
    validate_argv(argv, work)
    timeout = int(CFG.get("command_timeout_sec", 120))
    max_out = int(CFG.get("max_output_bytes", 262144))
    started = time.time()
    proc = subprocess.run(
        argv,
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={
            **os.environ,
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": "/home/ubuntu",
            "LANG": "C.UTF-8",
        },
    )
    out = (proc.stdout or "")[:max_out]
    err = (proc.stderr or "")[:max_out]
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "cwd": str(work),
        "argv": argv,
        "stdout": out,
        "stderr": err,
        "elapsed_sec": round(time.time() - started, 3),
        "truncated": len(proc.stdout or "") > max_out or len(proc.stderr or "") > max_out,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "IronLabAgent/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _deny(self, code: int, msg: str) -> None:
        json_response(self, code, {"ok": False, "error": msg})

    def do_GET(self) -> None:  # noqa: N802
        if not authorized(self):
            return self._deny(401, "unauthorized")
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path == "/health":
                return json_response(self, 200, {"ok": True, "service": "iron-lab-agent", "roots": CFG["roots"]})
            if u.path == "/v1/list":
                path = (qs.get("path") or [CFG["roots"][0]])[0]
                target = resolve_under_roots(path, write=False)
                if not target.exists():
                    return self._deny(404, f"not found: {target}")
                if target.is_file():
                    st = target.stat()
                    return json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "path": str(target),
                            "type": "file",
                            "size": st.st_size,
                            "mtime": int(st.st_mtime),
                        },
                    )
                entries = []
                for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                    try:
                        st = child.stat()
                        entries.append(
                            {
                                "name": child.name,
                                "path": str(child),
                                "type": "dir" if child.is_dir() else "file",
                                "size": st.st_size if child.is_file() else None,
                                "mtime": int(st.st_mtime),
                            }
                        )
                    except OSError:
                        continue
                return json_response(self, 200, {"ok": True, "path": str(target), "entries": entries})
            if u.path == "/v1/read":
                path = (qs.get("path") or [""])[0]
                if not path:
                    return self._deny(400, "path required")
                target = resolve_under_roots(path, write=False)
                if not target.is_file():
                    return self._deny(404, f"not a file: {target}")
                data = target.read_bytes()
                max_r = int(CFG.get("max_read_bytes", 1048576))
                truncated = len(data) > max_r
                text = data[:max_r].decode("utf-8", errors="replace")
                return json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "path": str(target),
                        "size": len(data),
                        "truncated": truncated,
                        "content": text,
                    },
                )
            if u.path == "/v1/git":
                path = (qs.get("path") or [CFG["roots"][0]])[0]
                action = (qs.get("action") or ["status"])[0]
                if action == "status":
                    return json_response(self, 200, run_argv(["git", "status", "--short", "--branch"], path))
                if action == "diff":
                    return json_response(self, 200, run_argv(["git", "diff", "--", "."], path))
                if action == "log":
                    return json_response(self, 200, run_argv(["git", "log", "-n", "15", "--oneline"], path))
                return self._deny(400, f"unknown git action: {action}")
            return self._deny(404, "not found")
        except PermissionError as e:
            return self._deny(403, str(e))
        except Exception as e:  # noqa: BLE001
            return self._deny(500, str(e))

    def do_POST(self) -> None:  # noqa: N802
        if not authorized(self):
            return self._deny(401, "unauthorized")
        u = urlparse(self.path)
        try:
            body = read_json(self)
            if u.path == "/v1/run":
                argv = body.get("argv")
                if not argv and body.get("command"):
                    # convenience: split simple commands without shell
                    argv = str(body["command"]).split()
                cwd = body.get("cwd")
                return json_response(self, 200, run_argv(list(argv), cwd))
            if u.path == "/v1/service":
                name = str(body.get("name") or "")
                action = str(body.get("action") or "status")
                if name not in CFG["services"]:
                    return self._deny(403, f"service not allowlisted: {name}")
                if action not in {"status", "is-active", "restart", "reload"}:
                    return self._deny(400, f"action not allowed: {action}")
                # nginx reload via systemctl reload nginx
                return json_response(self, 200, run_argv(["systemctl", action, name], CFG["roots"][0]))
            return self._deny(404, "not found")
        except subprocess.TimeoutExpired:
            return self._deny(504, "command timed out")
        except PermissionError as e:
            return self._deny(403, str(e))
        except Exception as e:  # noqa: BLE001
            return self._deny(500, str(e))

    def do_PUT(self) -> None:  # noqa: N802
        if not authorized(self):
            return self._deny(401, "unauthorized")
        u = urlparse(self.path)
        try:
            if u.path != "/v1/write":
                return self._deny(404, "not found")
            body = read_json(self)
            path = str(body.get("path") or "")
            content = body.get("content")
            if not path or content is None:
                return self._deny(400, "path and content required")
            if not isinstance(content, str):
                return self._deny(400, "content must be a string")
            max_w = int(CFG.get("max_write_bytes", 1048576))
            data = content.encode("utf-8")
            if len(data) > max_w:
                return self._deny(413, f"content exceeds max_write_bytes ({max_w})")
            target = resolve_under_roots(path, write=True)
            # refuse writes outside files that look like secrets
            name = target.name.lower()
            if name in {".env", "credentials.json", "id_rsa", "id_ed25519"} or name.endswith(".pem"):
                return self._deny(403, f"refusing to write sensitive file: {target.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            bak = None
            if body.get("backup", True):
                bak = backup_file(target)
            target.write_bytes(data)
            return json_response(
                self,
                200,
                {"ok": True, "path": str(target), "bytes": len(data), "backup": bak},
            )
        except PermissionError as e:
            return self._deny(403, str(e))
        except Exception as e:  # noqa: BLE001
            return self._deny(500, str(e))


def main() -> None:
    if not TOKEN:
        raise SystemExit("IRON_LAB_TOKEN is required")
    port = int(CFG.get("port", 8793))
    hosts = discover_listen_hosts(CFG.get("listen", "docker+local"))
    servers: list[ThreadingHTTPServer] = []
    for host in hosts:
        httpd = ThreadingHTTPServer((host, port), Handler)
        servers.append(httpd)
        print(f"iron-lab-agent listening on http://{host}:{port}", flush=True)

    import threading

    # Serve all but the last in background threads; block on the last.
    for httpd in servers[:-1]:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    servers[-1].serve_forever()


if __name__ == "__main__":
    main()
