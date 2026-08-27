# Iron Lab Agent + Open WebUI Tool

Opção A: a WebUI chama tools Python que falam com um agent local no Ubuntu.

| Peça | Onde | Porta |
|------|------|-------|
| `iron-lab-agent` | host (systemd) | `127.0.0.1:8793` |
| Tool `iron_lab_host` | Open WebUI Workspace | via `host.docker.internal:8793` |

## O que a Tool faz

- `lab_list` / `lab_read` / `lab_write` — arquivos sob allowlist (`~/iron-tools`, …)
- `lab_run` — comandos allowlisted (`git`, `docker compose`, `rg`, `systemctl` restrito, …)
- `lab_service` — `status|restart|reload` de `open-webui`, `iron-hub`, `qwen-uncensored`, `nginx`, `iron-lab-agent`
- `lab_git_status` / `lab_git_diff`

## Segurança

- Agent só escuta em `127.0.0.1`
- Auth por `IRON_LAB_TOKEN` (Bearer)
- Paths e binários allowlisted (`config.json` + `agent.py`)
- Writes criam `.bak-<timestamp>`; bloqueia `.env` / keys / `.pem`

## Deploy

```bash
# 1) token
cd ~/iron-tools/iron-hub/services/iron-lab-agent
umask 077
openssl rand -hex 32 > /tmp/lab.token
printf 'IRON_LAB_TOKEN=%s\n' "$(cat /tmp/lab.token)" > .env
chmod 600 .env
rm -f /tmp/lab.token

# 2) systemd
sudo cp deploy/iron-lab-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iron-lab-agent

# 3) Open WebUI com tools
# (ENABLE_TOOLS=True no docker-compose) + recreate
cd ~/iron-tools/iron-hub/services/open-webui
docker compose up -d

# 4) registrar tool no OWUI
set -a && source ../iron-lab-agent/.env && set +a
docker cp ../iron-lab-agent/owui_tool.py open-webui:/tmp/owui_tool.py
docker cp ../iron-lab-agent/register_tool.py open-webui:/tmp/register_tool.py
docker exec -e IRON_LAB_TOKEN -e IRON_LAB_AGENT_URL=http://host.docker.internal:8793 \
  -w /tmp open-webui python3 /tmp/register_tool.py
```

No chat: use o modelo **Qwen Local 122B**, ative a tool **Iron Lab Host** (ou já vem no model), e peça por exemplo:

> Lista o conteúdo de `/home/ubuntu/iron-tools/iron-hub/services` e mostre o status do serviço open-webui.
