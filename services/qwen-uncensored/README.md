# Qwen3.5-27B Instruct-Uncensored (n0ctyx) — local API (llama.cpp)

OpenAI-compatible endpoint for Iron Hub tools / MAVERICK / Open WebUI.

Runtime: **llama.cpp** (Vulkan, dual AMD V520) via `qwen-uncensored.service`.

## Endpoint

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:8080/v1` |
| Model (alias) | `qwen3.5-27b-uncensored-aggressive` (legacy alias kept for Strix) |
| Weights | `/nvme/models/Qwen3.5-27B-Instruct-Uncensored/…-Q5_K_M.gguf` |
| Source | `n0ctyx/Qwen3.5-27B-Instruct-Uncensored` |
| Context (`-c`) | `262144` (q4_0 KV + FIT) |
| Default `n_predict` | unset (client `max_tokens` controls length) |
| API key | contents of `~/.config/llama/api_key` (`source …/env.sh` exports it) |

LiteLLM / Strix / MAVERICK model id:

```text
openai/qwen3.5-27b-uncensored-aggressive
```

Open WebUI workspace id: `qwen-local` (base = alias acima).

## Ops

```bash
sudo systemctl status qwen-uncensored
source /home/ubuntu/iron-tools/iron-hub/services/qwen-uncensored/env.sh

curl -sS http://127.0.0.1:8080/v1/models | jq '.data[0].id'
curl -sS http://127.0.0.1:8080/v1/chat/completions \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "qwen3.5-27b-uncensored-aggressive",
    "messages": [{"role":"user","content":"2+2="}],
    "max_tokens": 16
  }'
```

Unit + drop-ins:

- `deploy/qwen-uncensored.service` (sync → `/etc/systemd/system/`)
- `/etc/systemd/system/qwen-uncensored.service.d/ctx.conf` → `CTX=262144`
- `/etc/systemd/system/qwen-uncensored.service.d/n-predict.conf` → no server cap

> O `docker-compose.yml` legado (Ollama :8780 / 14B) **não** é o path de produção. Use o systemd + `qwen-uncensored-serve`.
