"""Casino_bot runtime: health console + Telegram polling (lab mode)."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

STARTED_AT = time.time()
STATE = {
    "service": "casino-bot",
    "mode": "lab",
    "telegram": "starting",
    "telegram_username": None,
    "telegram_error": None,
    "payments": "disabled",
    "db_users": 0,
}

HOST = os.getenv("STATUS_HOST", "0.0.0.0")
PORT = int(os.getenv("STATUS_PORT", "8011"))
DB_PATH = os.getenv("DB_PATH", "bebra.db")


def _token_ok(token: str) -> bool:
    if not token or ":" not in token:
        return False
    left, right = token.split(":", 1)
    return left.isdigit() and len(right) >= 20


def _db_users() -> int:
    path = Path(DB_PATH)
    if not path.exists():
        return 0
    try:
        conn = sqlite3.connect(path)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            if not row or row[0] == 0:
                return 0
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return 0


def snapshot() -> dict:
    STATE["db_users"] = _db_users()
    STATE["uptime_s"] = int(time.time() - STARTED_AT)
    telegram = STATE["telegram"]
    status = "ok" if telegram == "polling" else "degraded"
    return {"status": status, **STATE}


HTML = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Casino Bot — Iron Lab</title>
  <style>
    :root { --bg:#07090d; --card:#10151c; --line:#1e2833; --cyan:#00d9ff; --muted:#8b95a3; --ok:#4ade80; --warn:#facc15; --bad:#ff3b45; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: ui-sans-serif, system-ui, sans-serif; background: radial-gradient(1200px 500px at 10% -10%, #123 0%, var(--bg) 55%); color:#e8edf2; }
    main { max-width: 920px; margin: 48px auto; padding: 0 20px; }
    h1 { font-size: 22px; letter-spacing: .04em; margin: 0 0 6px; }
    .sub { color: var(--muted); margin-bottom: 28px; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); gap: 12px; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }
    .k { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .12em; }
    .v { font-size: 20px; margin-top: 8px; font-variant-numeric: tabular-nums; }
    .ok { color: var(--ok); } .warn { color: var(--warn); } .bad { color: var(--bad); }
    pre { background:#0b0f14; border:1px solid var(--line); border-radius:10px; padding:14px; overflow:auto; color:#9fb3c8; font-size:12px; }
    a { color: var(--cyan); }
  </style>
</head>
<body>
  <main>
    <h1>CASINO BOT <span style="color:var(--cyan)">LAB</span></h1>
    <p class="sub">Telegram casino (BotYanis/Casino_bot) — pagamentos reais desligados. Demo/jogos só com token próprio.</p>
    <div class="grid">
      <div class="card"><div class="k">Health</div><div class="v" id="health">…</div></div>
      <div class="card"><div class="k">Telegram</div><div class="v" id="tg">…</div></div>
      <div class="card"><div class="k">Pagamentos</div><div class="v">desligados</div></div>
      <div class="card"><div class="k">Usuários SQLite</div><div class="v" id="users">…</div></div>
    </div>
    <p class="sub" style="margin-top:24px">JSON</p>
    <pre id="json">carregando…</pre>
  </main>
  <script>
    async function tick() {
      const r = await fetch('/api/health');
      const d = await r.json();
      const cls = d.telegram === 'polling' ? 'ok' : 'warn';
      document.getElementById('health').className = 'v ' + (d.status === 'ok' ? 'ok' : 'warn');
      document.getElementById('health').textContent = d.status;
      document.getElementById('tg').className = 'v ' + cls;
      document.getElementById('tg').textContent = d.telegram_username ? ('@' + d.telegram_username) : d.telegram;
      document.getElementById('users').textContent = d.db_users;
      document.getElementById('json').textContent = JSON.stringify(d, null, 2);
    }
    tick(); setInterval(tick, 5000);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path in ("/api/health", "/health"):
            payload = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(404, b'{"error":"not found"}', "application/json")


def start_status() -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"[casino-bot] status on http://{HOST}:{PORT}/", flush=True)
    return httpd


def start_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not _token_ok(token):
        STATE["telegram"] = "awaiting_token"
        STATE["telegram_error"] = "Defina TELEGRAM_BOT_TOKEN no .env (BotFather)."
        print("[casino-bot] no Telegram token — status console only", flush=True)
        return

    try:
        import requests

        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=15)
        data = r.json()
        if not data.get("ok"):
            STATE["telegram"] = "invalid_token"
            STATE["telegram_error"] = str(data.get("description", "getMe failed"))
            print(f"[casino-bot] getMe failed: {STATE['telegram_error']}", flush=True)
            return
        STATE["telegram_username"] = data["result"].get("username")
    except Exception as exc:
        STATE["telegram"] = "error"
        STATE["telegram_error"] = str(exc)
        print(f"[casino-bot] telegram probe failed: {exc}", flush=True)
        return

    # Upstream bot relies on `python main.py` (module __main__ + circular imports).
    import runpy

    STATE["telegram"] = "polling"
    print(f"[casino-bot] polling @{STATE['telegram_username']}", flush=True)
    runpy.run_path(str(Path(__file__).resolve().parent / "main.py"), run_name="__main__")


if __name__ == "__main__":
    start_status()
    start_bot()
    while True:
        time.sleep(60)
