# Iron Open WebUI

Chat UI local apontando para o Ollama **qwen-uncensored** (`:8780`) com `qwen3-local:30b`.

| Setting | Value |
|---|---|
| URL | http://127.0.0.1:3080 |
| Ollama | http://127.0.0.1:8780 |
| Modelo padrão | `qwen3-local:30b` |
| Auth | desabilitada (lab interno) |

## Ops

```bash
cd /home/kali/open-webui
docker compose up -d
sudo systemctl enable --now open-webui.service
```

Dependência: `qwen-uncensored.service` (Ollama).

## Iron Hub

Card em http://127.0.0.1:3900 — categoria Infraestrutura / LLM.
